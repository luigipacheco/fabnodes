bl_info = {
    "name": "GeoSlicer",
    "author": "Luis Pacheco",
    "description": "Topology slicer and G-code export for geometry node toolpaths",
    "blender": (4, 0, 3),
    "version": (0, 1, 0),
    "location": "View3D > Sidebar > GeoSlicer",
    "category": "Import-Export"
}

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, BoolProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from .gcode_python import GCode
from . import slicer

# attribute storage type -> numpy dtype for foreach_get bulk reads
_ATTR_DTYPE = {'FLOAT': np.float32, 'INT': np.int32, 'BOOLEAN': bool}


def _attr_values(mesh, name, expected_len):
    """Bulk-read a scalar point attribute via foreach_get.
    Returns a list of native Python values, or None if unavailable."""
    att = mesh.attributes.get(name)
    if att is None or att.domain != 'POINT' or len(att.data) != expected_len:
        return None
    dt = _ATTR_DTYPE.get(att.data_type)
    if dt is None:                       # unusual type: slow but safe fallback
        try:
            return [d.value for d in att.data]
        except AttributeError:
            return None
    buf = np.empty(expected_len, dtype=dt)
    att.data.foreach_get("value", buf)
    return buf.tolist()                  # native types for formatting/branching


# ---- Property Group for Scene Settings ----
class GcodeExportProperties(PropertyGroup):
    mode: EnumProperty(
        name="Mode",
        description="G-code export mode",
        items=[('cnc', 'CNC', ''), ('3dp', '3D Printer', ''), ('draw', 'Drawing', ''), ('laser', 'Laser', '')]
    )
    position_source: EnumProperty(
        name="Position Source",
        description="Choose between object's global position or position attribute",
        items=[
            ('global', 'Global Position', 'Use object vertices global positions'),
            ('attribute', 'Position Attribute', 'Use position attribute from geometry nodes')
        ],
        default='attribute'
    )
    scale: FloatProperty(name="Export Scale", description="Scale factor for exported coordinates", default=1000.0, step=100, precision=2)
    speed: FloatProperty(name="Speed", description="Feed rate", default=1000.0, step=10, precision=2, min=0.0, max=10000.0) 
    power: FloatProperty(name="Power", description="Laser power or similar", default=50.0, step=100, precision=2, min=0.0, max=1000.0)
    extrude: FloatProperty(name="Extrude", description="Extrusion amount", default=0.0, step=100, precision=2, min=0.0, max=1000.0)
    speeda: BoolProperty(name="Use Speed Attribute", default=False)
    powera: BoolProperty(name="Use Power Attribute", default=False)
    extrudea: BoolProperty(name="Use Extrude Attribute", default=False)
    customize: BoolProperty(name="Custom Start/End G-code", default=False)
    start_gcode: PointerProperty(name="Start G-code", type=bpy.types.Text)
    end_gcode: PointerProperty(name="End G-code", type=bpy.types.Text)


# ---- UI Panel ----
class VIEW3D_PT_gcode_exporter(Panel):
    bl_label = "GeoSlicer"
    bl_idname = "VIEW3D_PT_gcode_exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoSlicer'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.geoslicer_props

        layout.prop(scene_props, "mode")
        
        # Position source and scale
        box = layout.box()
        box.label(text="Position Settings:", icon='ORIENTATION_GLOBAL')
        box.prop(scene_props, "position_source")
        box.prop(scene_props, "scale", text="Export Scale")

        layout.label(text="Attributes & Global Values:")

        # Speed Row
        row = layout.row(align=True)
        row.prop(scene_props, "speeda", text="Use 'speed' Attribute")
        sub = row.row(align=True)
        sub.enabled = not scene_props.speeda
        sub.prop(scene_props, "speed", text="Speed (F)", slider=True)

        # Extrude Row
        row = layout.row(align=True)
        row.prop(scene_props, "extrudea", text="Use 'extrude' Attribute")
        sub = row.row(align=True)
        sub.enabled = not scene_props.extrudea
        sub.prop(scene_props, "extrude", text="Extrude (E)", slider=True)

        # Power Row
        row = layout.row(align=True)
        row.prop(scene_props, "powera", text="Use 'power' Attribute")
        sub = row.row(align=True)
        sub.enabled = not scene_props.powera
        sub.prop(scene_props, "power", text="Power (S)", slider=True)

        layout.separator()

        # Custom G-code Section
        layout.prop(scene_props, "customize", text="Custom Start/End")
        if scene_props.customize:
            layout.prop(scene_props, "start_gcode", text="START")
            layout.prop(scene_props, "end_gcode", text="END")

        layout.operator("object.gcode_export", text="Export G-code")


class VIEW3D_PT_gcode_help(Panel):
    bl_label = "Help"
    bl_idname = "VIEW3D_PT_gcode_help"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoSlicer'
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "VIEW3D_PT_gcode_exporter"

    def draw(self, context):
        layout = self.layout
        
        # Position Source Info
        layout.label(text="Position Sources:", icon='ORIENTATION_GLOBAL')
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Global Position:", icon='OBJECT_ORIGIN')
        col.label(text="  Uses mesh vertex positions", icon='BLANK1')
        col.label(text="Position Attribute:", icon='NODETREE')
        col.label(text="  Uses geometry nodes position", icon='BLANK1')
        
        layout.separator()
        
        layout.label(text="Required Attribute:", icon='FORCE_FORCE')
        box = layout.box()
        box.label(text="• position (Vector)", icon='DOT')
        box.label(text="  Only needed if using Position Attribute", icon='BLANK1')
        
        layout.label(text="Optional Attributes:", icon='FORCE_LENNARDJONES')
        box = layout.box()
        col = box.column(align=True)
        col.label(text="• speed (Float)", icon='DOT')
        col.label(text="  Feed rate in units/min", icon='BLANK1')
        
        col.label(text="• extrude (Float)", icon='DOT')
        col.label(text="  Extrusion amount for 3D printing", icon='BLANK1')
        
        col.label(text="• power (Float)", icon='DOT')
        col.label(text="  Power value for laser/plasma", icon='BLANK1')
        
        col.label(text="• draw (Boolean)", icon='DOT')
        col.label(text="  True/False for pen up/down", icon='BLANK1')

        layout.separator()
        layout.label(text="Usage Tips:", icon='INFO')
        box = layout.box()
        col = box.column(align=True)
        col.label(text="1. Choose position source")
        col.label(text="2. Add Geometry Nodes if using attributes")
        col.label(text="3. Create needed attributes")
        col.label(text="4. Enable checkboxes to use attributes")
        col.label(text="5. Values override global settings")


# ---- Operator to Export G-code ----
class OBJECT_OT_gcode_export(Operator):
    bl_idname = "object.gcode_export"
    bl_label = "Export G-code"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene_props = context.scene.geoslicer_props
        obj = context.object

        if not obj:
            self.report({"WARNING"}, "No object selected.")
            return {"CANCELLED"}

        filename = f"{obj.name}.gcode"

        # Get user settings
        mode = scene_props.mode
        scale_factor = scene_props.scale
        speed_global = scene_props.speed
        extrude_global = scene_props.extrude
        power_global = scene_props.power
        use_custom_gcode = scene_props.customize
        position_source = scene_props.position_source

        gcode_program = GCode(program_name=obj.name, mode=mode)

        # Custom start G-code
        if use_custom_gcode and scene_props.start_gcode:
            gcode_program.commands = scene_props.start_gcode.as_string().split('\n')
        else:
            gcode_program.set_speed(speed_global)

        world_matrix = obj.matrix_world
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.data
        n_points = len(mesh.vertices)

        # ---- bulk position read (foreach_get) + one batched transform ----
        if position_source == 'global':
            if n_points == 0:
                self.report({"WARNING"}, "No vertices found in the mesh.")
                return {"CANCELLED"}
            buf = np.empty(n_points * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", buf)
            pts = buf.reshape(-1, 3).astype(np.float64)
            m = np.array(world_matrix, dtype=np.float64)
            pts = pts @ m[:3, :3].T + m[:3, 3]      # all points at once
        else:  # position_source == 'attribute'
            att = mesh.attributes.get("position")
            if att is None or len(att.data) == 0:
                self.report({"WARNING"}, "No position attribute found. Switch to Global Position or add position attribute.")
                return {"CANCELLED"}
            buf = np.empty(len(att.data) * 3, dtype=np.float32)
            att.data.foreach_get("vector", buf)
            pts = buf.reshape(-1, 3).astype(np.float64)
            n_points = len(att.data)

        positions = (pts * scale_factor).tolist()

        # ---- bulk attribute reads (only when enabled) ----
        speeds   = _attr_values(mesh, "speed",   n_points) if scene_props.speeda   else None
        extrudes = _attr_values(mesh, "extrude", n_points) if scene_props.extrudea else None
        powers   = _attr_values(mesh, "power",   n_points) if scene_props.powera   else None
        draws    = _attr_values(mesh, "draw",    n_points)

        print(f"Exporting {len(positions)} movements...")

        # plain O(n) emission loop - string building is list-based (O(n) total)
        for i, pos in enumerate(positions):
            gcode_program.move_linear(
                pos[0], pos[1], pos[2],
                speed=speeds[i] if speeds is not None else speed_global,
                extrude=extrudes[i] if extrudes is not None else extrude_global,
                power=powers[i] if powers is not None else power_global,
                draw=bool(draws[i]) if draws is not None else False,
            )

        # Custom end G-code
        if use_custom_gcode and scene_props.end_gcode:
            gcode_program.commands.extend(scene_props.end_gcode.as_string().split('\n'))
        else:
            gcode_program.end_program()

        # Save to Blender text editor
        if filename in bpy.data.texts:
            bpy.data.texts[filename].clear()
        else:
            bpy.data.texts.new(filename)
        bpy.data.texts[filename].write('\n'.join(gcode_program.commands))

        print(f"GCode program saved as '{filename}' in Blender text editor.")
        self.report({"INFO"}, f"G-code saved as '{filename}'")
        return {"FINISHED"}


# ---- Registration ----
def register():
    bpy.utils.register_class(GcodeExportProperties)
    bpy.types.Scene.geoslicer_props = bpy.props.PointerProperty(type=GcodeExportProperties)
    bpy.utils.register_class(VIEW3D_PT_gcode_exporter)
    bpy.utils.register_class(VIEW3D_PT_gcode_help)
    bpy.utils.register_class(OBJECT_OT_gcode_export)
    slicer.register()


def unregister():
    slicer.unregister()
    del bpy.types.Scene.geoslicer_props
    bpy.utils.unregister_class(OBJECT_OT_gcode_export)
    bpy.utils.unregister_class(VIEW3D_PT_gcode_help)
    bpy.utils.unregister_class(VIEW3D_PT_gcode_exporter)
    bpy.utils.unregister_class(GcodeExportProperties)


if __name__ == "__main__":
    register()