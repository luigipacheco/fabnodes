"""
GeoSlicer Topology Slicer
========================
Non-planar slicing strategies (PLANAR | GEODESIC | VASE | WEIGHT) that turn a
mesh into ordered toolpath curves, plus a converter to an ordered point mesh
with geoslicer attributes (draw, path) ready for G-code export.

Numpy-vectorized core; scipy is used automatically if installed.
"""

import bpy
import bmesh
import heapq
import numpy as np
from collections import defaultdict
from mathutils import Vector, kdtree

try:
    from scipy.sparse import csr_matrix as _csr
    from scipy.sparse.csgraph import dijkstra as _sp_dijkstra
except Exception:
    _csr = None

MAX_LAYERS = 3000


# ─────────────────────────────────────────────────────────────────────────────
#  MESH ARRAYS (extracted once, all per-layer math is vectorized)
# ─────────────────────────────────────────────────────────────────────────────

class MeshArrays:
    def __init__(self, bm):
        self.n    = len(bm.verts)
        self.V    = np.array([v.co for v in bm.verts], dtype=np.float64)
        self.E    = np.array([(e.verts[0].index, e.verts[1].index)
                              for e in bm.edges], dtype=np.int64)
        self.elen = np.linalg.norm(self.V[self.E[:, 0]] - self.V[self.E[:, 1]], axis=1)
        self.F    = np.array([(f.verts[0].index, f.verts[1].index, f.verts[2].index)
                              for f in bm.faces], dtype=np.int64)
        self.FE   = np.array([(f.edges[0].index, f.edges[1].index, f.edges[2].index)
                              for f in bm.faces], dtype=np.int64)
        self._adj   = None
        self._graph = None

    def adjacency(self):
        if self._adj is None:
            adj = [[] for _ in range(self.n)]
            for (i, j), w in zip(self.E.tolist(), self.elen.tolist()):
                adj[i].append((j, w))
                adj[j].append((i, w))
            self._adj = adj
        return self._adj


def _dijkstra(ma, seed_indices):
    """Multi-source shortest path. Returns np.array (inf = unreachable)."""
    seeds = list(set(seed_indices))
    if _csr is not None:
        if ma._graph is None:
            i, j, w = ma.E[:, 0], ma.E[:, 1], ma.elen
            ma._graph = _csr((np.r_[w, w], (np.r_[i, j], np.r_[j, i])),
                             shape=(ma.n, ma.n))
        return _sp_dijkstra(ma._graph, directed=False, indices=seeds, min_only=True)
    adj  = ma.adjacency()
    INF  = float('inf')
    dist = [INF] * ma.n
    heap = []
    for vi in seeds:
        dist[vi] = 0.0
        heap.append((0.0, vi))
    heapq.heapify(heap)
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return np.array(dist)


# ─────────────────────────────────────────────────────────────────────────────
#  GEOMETRY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_boundary_loops(bm):
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if not boundary_edges:
        return []
    v2be = defaultdict(list)
    for e in boundary_edges:
        v2be[e.verts[0].index].append(e)
        v2be[e.verts[1].index].append(e)
    visited, loops = set(), []
    for start_e in boundary_edges:
        if start_e.index in visited:
            continue
        verts, cur_e, cur_v = [], start_e, start_e.verts[0]
        while cur_e.index not in visited:
            visited.add(cur_e.index)
            verts.append(cur_v.index)
            nv  = cur_e.other_vert(cur_v)
            nxt = [e for e in v2be[nv.index] if e.index not in visited]
            if not nxt:
                verts.append(nv.index)
                break
            cur_v, cur_e = nv, nxt[0]
        z_avg = sum(bm.verts[vi].co.z for vi in verts) / max(len(verts), 1)
        loops.append({"vert_indices": verts, "z_avg": z_avg})
    loops.sort(key=lambda l: l["z_avg"])
    return loops


def _signed_area_xy(pts):
    n, area = len(pts), 0.0
    if n < 3:
        return 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i].x * pts[j].y - pts[j].x * pts[i].y
    return area * 0.5


def _ensure_ccw(chain):
    if _signed_area_xy(chain) < 0.0:
        chain.reverse()
    return chain


def _iso_contour(ma, norm, t):
    """Vectorized iso-line extraction. Returns [(points, closed)]."""
    d0 = norm[ma.E[:, 0]]
    d1 = norm[ma.E[:, 1]]
    crossed = (d0 < t) != (d1 < t)
    idx = np.nonzero(crossed)[0]
    if idx.size < 2:
        return []
    dd0, dd1 = d0[idx], d1[idx]
    denom = dd1 - dd0
    safe  = np.where(np.abs(denom) > 1e-12, denom, 1.0)
    alpha = np.clip(np.where(np.abs(denom) > 1e-12, (t - dd0) / safe, 0.5), 0.0, 1.0)
    P0 = ma.V[ma.E[idx, 0]]
    P  = P0 + alpha[:, None] * (ma.V[ma.E[idx, 1]] - P0)
    pos = {int(e): k for k, e in enumerate(idx)}

    fc  = crossed[ma.FE]
    two = np.nonzero(fc.sum(axis=1) == 2)[0]
    conn = defaultdict(list)
    for row, mask in zip(ma.FE[two].tolist(), fc[two].tolist()):
        pair = [row[k] for k in range(3) if mask[k]]
        conn[pair[0]].append(pair[1])
        conn[pair[1]].append(pair[0])

    visited = set()

    def walk(start, nxt):
        edges = [start]
        prev, cur = start, nxt
        while True:
            if cur == start:
                return edges, True
            edges.append(cur)
            following = [n for n in conn[cur] if n != prev]
            if not following:
                return edges, False
            prev, cur = cur, following[0]

    chains = []
    for ei in pos:
        if ei in visited or len(conn.get(ei, ())) != 1:
            continue
        edges, closed = walk(ei, conn[ei][0])
        visited.update(edges)
        chains.append(([Vector(P[pos[e]]) for e in edges], closed))
    for ei in pos:
        if ei in visited:
            continue
        cs = conn.get(ei, ())
        if not cs:
            visited.add(ei)
            continue
        edges, closed = walk(ei, cs[0])
        visited.update(edges)
        chains.append(([Vector(P[pos[e]]) for e in edges], closed))
    return [c for c in chains if len(c[0]) >= 2]


def _face_gradient_mags(ma, norm):
    """|grad f| per face (field units per world unit), fully vectorized."""
    p0 = ma.V[ma.F[:, 0]]
    e1 = ma.V[ma.F[:, 1]] - p0
    e2 = ma.V[ma.F[:, 2]] - p0
    N  = np.cross(e1, e2)
    nn = np.einsum('ij,ij->i', N, N)
    df1 = norm[ma.F[:, 1]] - norm[ma.F[:, 0]]
    df2 = norm[ma.F[:, 2]] - norm[ma.F[:, 0]]
    g = np.cross(e2, N) * df1[:, None] + np.cross(N, e1) * df2[:, None]
    g /= np.where(nn > 1e-18, nn, 1.0)[:, None]
    mags = np.linalg.norm(g, axis=1)
    mags[nn <= 1e-18] = 0.0
    return mags


def _resample_chain(pts, closed, seg_len):
    if seg_len <= 0.0 or len(pts) < 3:
        return pts
    src = list(pts) + ([pts[0]] if closed else [])
    cum = [0.0]
    for i in range(len(src) - 1):
        cum.append(cum[-1] + (src[i + 1] - src[i]).length)
    total = cum[-1]
    if total <= seg_len:
        return pts
    if closed:
        n = max(int(round(total / seg_len)), 3)
        targets = [total * i / n for i in range(n)]
    else:
        n = max(int(round(total / seg_len)), 1)
        targets = [total * i / n for i in range(n + 1)]
    out, j = [], 0
    for tt in targets:
        while j < len(cum) - 2 and cum[j + 1] < tt:
            j += 1
        seg = cum[j + 1] - cum[j]
        a = (tt - cum[j]) / seg if seg > 1e-12 else 0.0
        out.append(src[j].lerp(src[j + 1], a))
    return out


def _align_seam(chain, ref):
    if ref is None or len(chain) < 3:
        return chain
    best = min(range(len(chain)), key=lambda i: (chain[i] - ref).length_squared)
    return chain[best:] + chain[:best]


def _layer_z_centroid(chains):
    total, count = 0.0, 0
    for chain in chains:
        for pt in chain:
            total += pt.z
            count += 1
    return total / count if count else 0.0


def _measure_spacing(prev_pts, chains):
    """True layer height: nearest distance from new contour points to previous layer."""
    kd = kdtree.KDTree(len(prev_pts))
    for i, p in enumerate(prev_pts):
        kd.insert(p, i)
    kd.balance()
    dmin, dmax, dsum, n = float('inf'), 0.0, 0.0, 0
    for pts, _closed in chains:
        for p in pts:
            _co, _i, d = kd.find(p)
            if d < dmin: dmin = d
            if d > dmax: dmax = d
            dsum += d
            n += 1
    if n == 0:
        return 0.0, 0.0, 0.0
    return dmin, dmax, dsum / n


def _add_spline(cdata, pts, closed, spline_type):
    sp = cdata.splines.new(spline_type)
    sp.points.add(len(pts) - 1)
    for k, pt in enumerate(pts):
        sp.points[k].co     = (pt.x, pt.y, pt.z, 1.0)
        sp.points[k].weight = 1.0
    if spline_type == 'NURBS':
        sp.order_u = min(4, len(pts))
        sp.use_endpoint_u = not closed
    sp.use_cyclic_u = closed


# ─────────────────────────────────────────────────────────────────────────────
#  STRATEGY REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class SlicerStrategy:
    """A strategy builds a per-vertex scalar field in [0, 1] (numpy array).
    The shared pipeline extracts iso-contours of that field."""
    id = ""
    label = ""
    descr = ""
    include_bottom = False   # inject bottom boundary loop as first layer
    include_top    = False   # inject top boundary loop as last layer (iso-lines only)

    def build_field(self, ma, bm, obj, props, loops):
        raise NotImplementedError


class PlanarStrategy(SlicerStrategy):
    id, label = 'PLANAR', "Planar"
    descr = "Horizontal slices by Z height (classic slicing)"

    def build_field(self, ma, bm, obj, props, loops):
        z = ma.V[:, 2]
        lo = z.min()
        rng = max(z.max() - lo, 1e-12)
        return (z - lo) / rng, {}


class GeodesicStrategy(SlicerStrategy):
    id, label = 'GEODESIC', "Geodesic"
    descr = "Equal surface (geodesic) distance from the bottom"
    include_bottom = True

    def build_field(self, ma, bm, obj, props, loops):
        if loops:
            seeds = loops[0]["vert_indices"]
        else:
            z = ma.V[:, 2]
            seed_z = z.min() + (z.max() - z.min()) * props.bottom_threshold / 100.0
            seeds = np.nonzero(z <= seed_z)[0].tolist()
        d = _dijkstra(ma, seeds)
        finite = np.isfinite(d)
        max_d = float(d[finite].max()) if finite.any() else 1.0
        return np.where(finite, d / max_d, 1.0), {"max_geo": max_d}


class VaseStrategy(SlicerStrategy):
    id, label = 'VASE', "Vase"
    descr = "Equal geodesic fraction between bottom and top boundaries (topological slice)"
    include_bottom = True
    include_top    = True

    def build_field(self, ma, bm, obj, props, loops):
        if len(loops) < 2:
            raise RuntimeError(f"Vase needs >= 2 boundary loops (found {len(loops)}).")
        db = _dijkstra(ma, loops[0]["vert_indices"])
        dt = _dijkstra(ma, loops[-1]["vert_indices"])
        b  = np.where(np.isfinite(db), db, 0.0)
        tt = np.where(np.isfinite(dt), dt, 0.0)
        s  = b + tt
        field = np.where(s > 1e-12, b / np.where(s > 1e-12, s, 1.0), 0.5)
        iters = props.harmonic_iterations
        if iters > 0:
            bot = np.array(sorted(set(loops[0]["vert_indices"])), dtype=np.int64)
            top = np.array(sorted(set(loops[-1]["vert_indices"])), dtype=np.int64)
            field[bot] = 0.0
            field[top] = 1.0
            Ei, Ej = ma.E[:, 0], ma.E[:, 1]
            deg = np.zeros(ma.n)
            np.add.at(deg, Ei, 1.0)
            np.add.at(deg, Ej, 1.0)
            deg = np.maximum(deg, 1.0)
            for _ in range(iters):
                acc = np.zeros(ma.n)
                np.add.at(acc, Ei, field[Ej])
                np.add.at(acc, Ej, field[Ei])
                new = acc / deg
                new[bot] = 0.0
                new[top] = 1.0
                field = new
        return field, {}


class WeightStrategy(SlicerStrategy):
    id, label = 'WEIGHT', "Weight"
    descr = "Iso-lines of a painted vertex-group weight (Tissue-style)"

    def build_field(self, ma, bm, obj, props, loops):
        vg = obj.vertex_groups.get(props.weight_group)
        if vg is None:
            raise RuntimeError("Pick a vertex group for the Weight strategy.")
        layer = bm.verts.layers.deform.active
        if layer is None:
            raise RuntimeError("Mesh has no vertex-group (deform) data.")
        gi = vg.index
        w  = np.array([v[layer].get(gi, 0.0) for v in bm.verts])
        lo, hi = float(w.min()), float(w.max())
        if hi - lo < 1e-9:
            raise RuntimeError(f"Group '{vg.name}' is constant - paint a gradient.")
        return (w - lo) / (hi - lo), {}


STRATEGIES      = (PlanarStrategy(), GeodesicStrategy(), VaseStrategy(), WeightStrategy())
STRATEGY_MAP    = {s.id: s for s in STRATEGIES}
_STRATEGY_ITEMS = [(s.id, s.label, s.descr) for s in STRATEGIES]


# ─────────────────────────────────────────────────────────────────────────────
#  PROPERTIES
# ─────────────────────────────────────────────────────────────────────────────

class TopoSlicerProps(bpy.types.PropertyGroup):
    target_object: bpy.props.PointerProperty(
        name="Mesh Object", type=bpy.types.Object,
        poll=lambda self, o: o.type == 'MESH',
        description="Mesh to slice (blank = active object)",
    )
    use_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers", default=True,
        description="Slice the evaluated mesh (subsurf, remesh, ...) - "
                    "what you actually see in the viewport",
    )

    strategy: bpy.props.EnumProperty(
        name="Strategy", items=_STRATEGY_ITEMS, default='GEODESIC',
    )

    layer_mode: bpy.props.EnumProperty(
        name="Layer Mode",
        items=[
            ('COUNT',  "Count",  "Fixed number of layers"),
            ('HEIGHT', "Height",
             "Uniform steps; layer count derived from Max Layer Height so "
             "spacing never exceeds it"),
        ],
        default='COUNT',
    )
    num_layers: bpy.props.IntProperty(name="Layers", default=20, min=2, max=500)
    max_layer_height: bpy.props.FloatProperty(
        name="Max Layer Height", default=0.02,
        min=0.0001, max=10.0, precision=4, step=1,
        description="Layer count is derived so worst-case spacing stays at or "
                    "below this (world units)",
    )
    bottom_threshold: bpy.props.FloatProperty(
        name="Bottom Seed %", default=2.0, min=0.01, max=20.0,
        step=10, precision=2,
        description="(Geodesic, closed meshes only) % of Z-height used as seeds",
    )
    harmonic_iterations: bpy.props.IntProperty(
        name="Extra Smoothing", default=0, min=0, max=1000,
        description="(Vase) optional Laplacian relaxation passes. 0 = pure "
                    "topological slice. Note: smoothing trades geodesic "
                    "spacing for smoothness",
    )
    weight_group: bpy.props.StringProperty(
        name="Vertex Group", default="",
        description="(Weight) vertex group whose weights define the slicing field",
    )

    resample_length: bpy.props.FloatProperty(
        name="Resample Length", default=0.0, min=0.0, max=10.0,
        precision=4, step=1,
        description="Resample contours to uniform segment length "
                    "(0 = raw iso-contour points). Even spacing = even extrusion",
    )
    align_seams: bpy.props.BoolProperty(
        name="Align Seams", default=True,
        description="Rotate each closed loop to start near the previous "
                    "layer's start point",
    )
    make_toolpath: bpy.props.BoolProperty(
        name="Auto Toolpath Mesh", default=False,
        description="Run Make Toolpath Mesh automatically after slicing",
    )
    keep_curves: bpy.props.BoolProperty(
        name="Keep Curves", default=True,
        description="Keep the <object>_curves preview object after making the "
                    "toolpath mesh (uncheck to go straight to the export mesh)",
    )

    spline_type: bpy.props.EnumProperty(
        name="Spline Type",
        items=[
            ('POLY',  "Poly",  "Linear segments - exact iso-contour, export-safe"),
            ('NURBS', "NURBS", "Smooth interpolation (points drift off-surface slightly)"),
        ],
        default='POLY',
    )
    curve_resolution: bpy.props.IntProperty(
        name="NURBS Resolution", default=12, min=1, max=128,
    )

    use_bevel: bpy.props.BoolProperty(name="Show Bevel", default=True)
    bevel_depth: bpy.props.FloatProperty(
        name="Bevel Radius", default=0.001,
        min=0.0, max=1.0, precision=4, step=1,
    )

    info_layers:   bpy.props.IntProperty(default=0, options={'HIDDEN'})
    info_open:     bpy.props.IntProperty(default=0, options={'HIDDEN'})
    info_min_dist: bpy.props.FloatProperty(default=0.0, options={'HIDDEN'})
    info_max_dist: bpy.props.FloatProperty(default=0.0, options={'HIDDEN'})
    info_ready:    bpy.props.BoolProperty(default=False, options={'HIDDEN'})


# ─────────────────────────────────────────────────────────────────────────────
#  OPERATOR
# ─────────────────────────────────────────────────────────────────────────────

class TOPOSLICE_OT_Run(bpy.types.Operator):
    bl_idname      = "toposlice.run"
    bl_label       = "Generate Slices"
    bl_description = "Run slicer -> <object>_curves, CCW, bottom-to-top"
    bl_options     = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props    = context.scene.topo_slicer
        strategy = STRATEGY_MAP[props.strategy]

        obj = props.target_object or context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No valid mesh - pick one or make it active.")
            return {'CANCELLED'}

        ob_eval = None
        if props.use_modifiers:
            deps    = context.evaluated_depsgraph_get()
            ob_eval = obj.evaluated_get(deps)
            me      = ob_eval.to_mesh()
        else:
            me = obj.data

        bm = bmesh.new()
        bm.from_mesh(me)
        if ob_eval is not None:
            ob_eval.to_mesh_clear()
        bm.transform(obj.matrix_world)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        bm.faces.index_update()

        ma    = MeshArrays(bm)
        loops = _find_boundary_loops(bm)

        try:
            norm, info = strategy.build_field(ma, bm, obj, props, loops)
        except RuntimeError as err:
            self.report({'ERROR'}, str(err))
            bm.free()
            return {'CANCELLED'}

        # ── collect layers: (t, [(pts, closed)], z_centroid) ────────────────
        all_layers = []
        bot_pts = None
        if strategy.include_bottom and loops:
            bot_pts = [bm.verts[vi].co.copy() for vi in loops[0]["vert_indices"]]
            all_layers.append((0.0, [(bot_pts, True)], _layer_z_centroid([bot_pts])))

        capped = False
        if props.layer_mode == 'HEIGHT':
            # uniform t-steps; count derived from Max Layer Height.
            # worst-case physical spacing per unit t = 1 / (robust low gradient)
            g_face = _face_gradient_mags(ma, norm)
            pos_g  = g_face[g_face > 1e-9]
            if pos_g.size:
                k = int(pos_g.size * 0.05)
                g_lo = float(np.partition(pos_g, k)[k])
            else:
                g_lo = 1.0
            n = max(int(np.ceil(1.0 / (g_lo * props.max_layer_height))), 2)
            if n > MAX_LAYERS:
                n, capped = MAX_LAYERS, True
        else:
            n = props.num_layers
        for i in range(1, n):
            t = i / n
            chains = _iso_contour(ma, norm, t)
            if chains:
                all_layers.append(
                    (t, chains, _layer_z_centroid([c[0] for c in chains])))

        if strategy.include_top and len(loops) >= 2:
            top = [bm.verts[vi].co.copy() for vi in loops[-1]["vert_indices"]]
            all_layers.append((1.0, [(top, True)], _layer_z_centroid([top])))

        bm.free()
        all_layers.sort(key=lambda x: x[0])

        # ── post-process: resample -> CCW -> seam align ─────────────────────
        seam_ref, cursor, processed, open_count = None, None, [], 0
        for t, chains, zc in all_layers:
            out = []
            for pts, closed in chains:
                pts = _resample_chain(pts, closed, props.resample_length)
                if closed:
                    pts = _ensure_ccw(pts)
                    if props.align_seams:
                        pts = _align_seam(pts, seam_ref)
                    cursor = pts[0]
                else:
                    open_count += 1
                    # ping-pong: continue from where the previous chain ended
                    if props.align_seams and cursor is not None and (
                            (pts[0] - cursor).length_squared >
                            (pts[-1] - cursor).length_squared):
                        pts = list(reversed(pts))
                    cursor = pts[-1]
                out.append((pts, closed))
            if out and out[0][1]:
                seam_ref = out[0][0][0]
            processed.append((t, out, zc))

        # ── spacing info: true nearest-point distance between layers ────────
        min_sp, max_sp = float('inf'), 0.0
        for i in range(1, len(processed)):
            prev = [p for c, _ in processed[i - 1][1] for p in c]
            if not prev or not processed[i][1]:
                continue
            s_min, s_max, _ = _measure_spacing(prev, processed[i][1])
            min_sp = min(min_sp, s_min)
            max_sp = max(max_sp, s_max)
        if min_sp == float('inf'):
            min_sp = max_sp = 0.0

        # ── build curve object ───────────────────────────────────────────────
        COLL_NAME = "Topology_Slices"
        coll = bpy.data.collections.get(COLL_NAME)
        if coll is None:
            coll = bpy.data.collections.new(COLL_NAME)
            context.scene.collection.children.link(coll)

        out_name = obj.name + "_curves"
        prev = bpy.data.objects.get(out_name)
        if prev is not None:
            prev_data = prev.data
            bpy.data.objects.remove(prev, do_unlink=True)
            if prev_data is not None and prev_data.users == 0:
                bpy.data.curves.remove(prev_data)

        cdata            = bpy.data.curves.new(out_name, 'CURVE')
        cdata.dimensions = '3D'
        cdata.resolution_u = (props.curve_resolution
                              if props.spline_type == 'NURBS' else 1)
        if props.use_bevel:
            cdata.bevel_mode       = 'ROUND'
            cdata.bevel_depth      = props.bevel_depth
            cdata.bevel_resolution = 4

        total_splines = 0
        for _, chains, _ in processed:
            for pts, closed in chains:
                _add_spline(cdata, pts, closed, props.spline_type)
                total_splines += 1

        cobj = bpy.data.objects.new(out_name, cdata)
        coll.objects.link(cobj)

        props.info_layers   = len(processed)
        props.info_open     = open_count
        props.info_min_dist = min_sp
        props.info_max_dist = max_sp
        props.info_ready    = True

        msg = (f"[{strategy.id}/{props.spline_type}] {len(processed)} layers | "
               f"{total_splines} splines | h {min_sp:.4f}-{max_sp:.4f}")
        warn = []
        if open_count:
            warn.append(f"{open_count} OPEN chains")
        if capped:
            warn.append(f"layer cap {MAX_LAYERS} hit")
        if warn:
            self.report({'WARNING'}, msg + " | " + ", ".join(warn))
        else:
            self.report({'INFO'}, msg)

        if props.make_toolpath:
            bpy.ops.toposlice.to_toolpath()
            if not props.keep_curves:
                cur = bpy.data.objects.get(out_name)
                if cur is not None:
                    cdat = cur.data
                    bpy.data.objects.remove(cur, do_unlink=True)
                    if cdat is not None and cdat.users == 0:
                        bpy.data.curves.remove(cdat)
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
#  PANEL
# ─────────────────────────────────────────────────────────────────────────────


class TOPOSLICE_OT_ToToolpath(bpy.types.Operator):
    bl_idname      = "toposlice.to_toolpath"
    bl_label       = "Make Toolpath Mesh"
    bl_description = ("Flatten the sliced curves into an ordered point mesh with "
                      "geoslicer attributes (draw, path) for G-code export")
    bl_options     = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.topo_slicer
        src_obj = props.target_object or context.active_object
        curve_obj = None
        if src_obj is not None:
            curve_obj = bpy.data.objects.get(src_obj.name + "_curves")
        if curve_obj is None and context.active_object \
                and context.active_object.type == 'CURVE':
            curve_obj = context.active_object
        if curve_obj is None or curve_obj.type != 'CURVE':
            self.report({'ERROR'}, "No sliced curves found - run Generate Slices first.")
            return {'CANCELLED'}

        verts, edges, draw_flags, path_idx = [], [], [], []
        nurbs_seen = False
        for si, sp in enumerate(curve_obj.data.splines):
            if sp.type == 'NURBS':
                nurbs_seen = True
            pts = [tuple(p.co[:3]) for p in sp.points]
            if len(pts) < 2:
                continue
            if sp.use_cyclic_u:
                pts.append(pts[0])              # close the loop in path order
            start = len(verts)
            verts.extend(pts)
            edges.extend((start + k, start + k + 1) for k in range(len(pts) - 1))
            draw_flags.extend([False] + [True] * (len(pts) - 1))  # first move = travel
            path_idx.extend([si] * len(pts))

        if not verts:
            self.report({'ERROR'}, "Curve object has no usable splines.")
            return {'CANCELLED'}

        base = (curve_obj.name[:-7] if curve_obj.name.endswith("_curves")
                else curve_obj.name)
        out_name = base + "_toolpath"
        prev = bpy.data.objects.get(out_name)
        if prev is not None:
            prev_data = prev.data
            bpy.data.objects.remove(prev, do_unlink=True)
            if prev_data is not None and prev_data.users == 0:
                bpy.data.meshes.remove(prev_data)

        mesh = bpy.data.meshes.new(out_name)
        mesh.from_pydata(verts, edges, [])
        a = mesh.attributes.new("draw", 'BOOLEAN', 'POINT')
        a.data.foreach_set("value", draw_flags)
        p = mesh.attributes.new("path", 'INT', 'POINT')
        p.data.foreach_set("value", path_idx)

        mobj = bpy.data.objects.new(out_name, mesh)
        coll = bpy.data.collections.get("Topology_Slices")
        (coll if coll is not None else context.scene.collection).objects.link(mobj)

        msg = f"'{out_name}': {len(verts)} points, vertex order = print order"
        if nurbs_seen:
            self.report({'WARNING'},
                        msg + " | NURBS control points used - slice with POLY "
                              "for exact paths")
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


class TOPOSLICE_PT_Panel(bpy.types.Panel):
    bl_label       = "Slicer"
    bl_idname      = "TOPOSLICE_PT_panel"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "GeoSlicer"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.topo_slicer
        ob = props.target_object or context.active_object

        box = layout.box()
        box.label(text="Target Mesh", icon='MESH_DATA')
        box.prop(props, "target_object", text="")
        box.prop(props, "use_modifiers")

        box = layout.box()
        box.label(text="Strategy", icon='FORCE_FORCE')
        box.prop(props, "strategy", text="")

        box = layout.box()
        box.label(text="Layer Settings", icon='SETTINGS')
        col = box.column(align=True)
        col.prop(props, "layer_mode", expand=True)
        col.separator(factor=0.5)
        if props.layer_mode == 'COUNT':
            col.prop(props, "num_layers", slider=True)
        else:
            col.prop(props, "max_layer_height")
        col.separator(factor=0.5)
        if props.strategy == 'GEODESIC':
            col.prop(props, "bottom_threshold")
        elif props.strategy == 'VASE':
            col.prop(props, "harmonic_iterations")
        elif props.strategy == 'WEIGHT':
            if ob and ob.type == 'MESH':
                col.prop_search(props, "weight_group", ob,
                                "vertex_groups", text="Group")
            else:
                col.label(text="Pick a mesh first", icon='ERROR')

        box = layout.box()
        box.label(text="Toolpath", icon='OUTLINER_OB_CURVE')
        col = box.column(align=True)
        col.prop(props, "resample_length")
        col.prop(props, "align_seams")
        col.prop(props, "make_toolpath")
        if props.make_toolpath:
            col.prop(props, "keep_curves")
        col.separator(factor=0.5)
        col.prop(props, "spline_type", expand=True)
        if props.spline_type == 'NURBS':
            col.prop(props, "curve_resolution", slider=True)

        box = layout.box()
        row = box.row()
        row.prop(props, "use_bevel", text="Bevel (Visualization)")
        if props.use_bevel:
            box.prop(props, "bevel_depth")

        layout.separator()
        layout.operator("toposlice.run", text="Generate Slices", icon='SORTBYEXT')
        layout.operator("toposlice.to_toolpath", text="Make Toolpath Mesh", icon='MESH_DATA')

        info = layout.box()
        info.scale_y = 0.8
        if props.info_ready:
            info.label(text=f"Layers: {props.info_layers}", icon='INFO')
            row = info.row(align=True)
            row.label(text=f"Min h: {props.info_min_dist:.4f}")
            row.label(text=f"Max h: {props.info_max_dist:.4f}")
            if props.info_open:
                info.label(text=f"{props.info_open} open chains!", icon='ERROR')
        else:
            info.label(text="Run to see slice info", icon='INFO')


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTER
# ─────────────────────────────────────────────────────────────────────────────

_CLASSES = [TopoSlicerProps, TOPOSLICE_OT_Run, TOPOSLICE_OT_ToToolpath, TOPOSLICE_PT_Panel]

def _unregister_stale():
    for name in ("TOPOSLICE_PT_Panel", "TOPOSLICE_OT_ToToolpath",
                 "TOPOSLICE_OT_Run", "TopoSlicerProps"):
        cls = getattr(bpy.types, name, None)
        if cls is not None:
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass

def register():
    _unregister_stale()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.topo_slicer = bpy.props.PointerProperty(type=TopoSlicerProps)

def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        del bpy.types.Scene.topo_slicer
    except Exception:
        pass

if __name__ == "__main__":
    register()
