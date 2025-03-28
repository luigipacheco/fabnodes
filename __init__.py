bl_info = {
    "name": "Fabnodes-Gcode Export",
    "author": "Luis Pacheco",
    "description": "Export geometry node toolpaths to G-code",
    "blender": (4, 0, 3),
    "version": (0, 0, 2),
    "location": "View3D > Sidebar > Fabnodes",
    "category": "Import-Export"
}

import bpy
from bpy.props import EnumProperty, FloatProperty, BoolProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from .gcode_python import GCode


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
    bl_label = "Fabnodes"
    bl_idname = "VIEW3D_PT_gcode_exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Fabnodes'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.fabnodes_props

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
    bl_category = 'Fabnodes'
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
        scene_props = context.scene.fabnodes_props
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

        positions = []
        if position_source == 'global':
            # Use global vertex positions - apply world matrix transformation
            mesh = eval_obj.data
            for vertex in mesh.vertices:
                global_pos = world_matrix @ vertex.co
                positions.append((global_pos.x * scale_factor, global_pos.y * scale_factor, global_pos.z * scale_factor))
        else:  # position_source == 'attribute'
            # Use position attribute directly - no world matrix transformation needed
            if "position" in eval_obj.data.attributes:
                for pos in eval_obj.data.attributes["position"].data:
                    # Use position values directly as they already include transformations
                    positions.append((pos.vector.x * scale_factor, pos.vector.y * scale_factor, pos.vector.z * scale_factor))

        if not positions:
            if position_source == 'attribute':
                self.report({"WARNING"}, "No position attribute found. Switch to Global Position or add position attribute.")
            else:
                self.report({"WARNING"}, "No vertices found in the mesh.")
            return {"CANCELLED"}

        # Retrieve optional attributes and verify data presence
        speeds = eval_obj.data.attributes.get("speed", None)
        extrudes = eval_obj.data.attributes.get("extrude", None)
        powers = eval_obj.data.attributes.get("power", None)
        draws = eval_obj.data.attributes.get("draw", None)  # Boolean attribute for drawing state

        speeds = speeds.data if speeds else [None] * len(positions)
        extrudes = extrudes.data if extrudes else [None] * len(positions)
        powers = powers.data if powers else [None] * len(positions)
        draws = draws.data if draws else [None] * len(positions)  # Default to no drawing

        print(f"Exporting {len(positions)} movements...")

        # Generate G-code with drawing state
        for i, pos in enumerate(positions):
            speed_value = speeds[i].value if (scene_props.speeda and speeds[i] and hasattr(speeds[i], 'value')) else speed_global
            extrude_value = extrudes[i].value if (scene_props.extrudea and extrudes[i] and hasattr(extrudes[i], 'value')) else extrude_global
            power_value = powers[i].value if (scene_props.powera and powers[i] and hasattr(powers[i], 'value')) else power_global
            draw_state = bool(draws[i].value) if (draws[i] and hasattr(draws[i], 'value')) else False  # Default to False

            gcode_program.move_linear(*pos, speed=speed_value, extrude=extrude_value, power=power_value, draw=draw_state)
            print(f"Moving to {pos} with speed={speed_value}, extrude={extrude_value}, power={power_value}, draw={draw_state}")

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
    bpy.types.Scene.fabnodes_props = bpy.props.PointerProperty(type=GcodeExportProperties)
    bpy.utils.register_class(VIEW3D_PT_gcode_exporter)
    bpy.utils.register_class(VIEW3D_PT_gcode_help)
    bpy.utils.register_class(OBJECT_OT_gcode_export)


def unregister():
    del bpy.types.Scene.fabnodes_props
    bpy.utils.unregister_class(OBJECT_OT_gcode_export)
    bpy.utils.unregister_class(VIEW3D_PT_gcode_help)
    bpy.utils.unregister_class(VIEW3D_PT_gcode_exporter)
    bpy.utils.unregister_class(GcodeExportProperties)


if __name__ == "__main__":
    register()