bl_info = {
    "name": "Fabnodes-Gcode Export",
    "author": "Luis Pacheco",
    "description": "Export geometry node toolpaths to G-code",
    "blender": (4, 0, 3),
    "version": (0, 1, 0),
    "category": "3D View"
}

import bpy
from bpy.props import EnumProperty, FloatProperty, BoolProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from .gcode_python import GCode


# ---- Property Group for Scene Settings ----
class FABNODES_Properties(PropertyGroup):
    mode: EnumProperty(
        name="Mode",
        description="G-code export mode",
        items=[('cnc', 'CNC', ''), ('3dp', '3D Printer', ''), ('draw', 'Drawing', ''), ('laser', 'Laser', '')]
    )
    speed: FloatProperty(name="Speed", description="Feed rate", default=50.0, step=100, precision=2, min=0.0, max=10000.0) 
    power: FloatProperty(name="Power", description="Laser power or similar", default=50.0, step=100, precision=2, min=0.0, max=1000.0)
    extrude: FloatProperty(name="Extrude", description="Extrusion amount", default=0.0, step=100, precision=2 , min=0.0, max=1000.0)
    speeda: BoolProperty(name="Use Speed Attribute", default=False)
    powera: BoolProperty(name="Use Power Attribute", default=False)
    extrudea: BoolProperty(name="Use Extrude Attribute", default=False)
    customize: BoolProperty(name="Custom Start/End G-code", default=False)
    start_gcode: PointerProperty(name="Start G-code", type=bpy.types.Text)
    end_gcode: PointerProperty(name="End G-code", type=bpy.types.Text)
    scale: FloatProperty(name="Export Scale", default=1000.0, step=100, precision=2)


# ---- UI Panel ----
class FABNODES_PT_ExporterPanel(Panel):
    bl_label = "Fabnodes Exporter"
    bl_idname = "FABNODES_PT_exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Fabnodes'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.fabnodes_props

        layout.prop(scene_props, "mode")
        layout.prop(scene_props, "scale", text="Export Scale")

        layout.label(text="Attributes & Global Values:")

        # Speed Row (Fix: Separate checkbox & slider)
        row = layout.row(align=True)
        row.prop(scene_props, "speeda", text="Use Speed Attribute")  # Checkbox always enabled
        sub = row.row(align=True)
        sub.enabled = not scene_props.speeda  # Only disable the slider, NOT the checkbox
        sub.prop(scene_props, "speed", text="Speed (F)", slider=True)

        # Extrude Row
        row = layout.row(align=True)
        row.prop(scene_props, "extrudea", text="Use Extrude Attribute")
        sub = row.row(align=True)
        sub.enabled = not scene_props.extrudea
        sub.prop(scene_props, "extrude", text="Extrude (E)", slider=True)

        # Power Row
        row = layout.row(align=True)
        row.prop(scene_props, "powera", text="Use Power Attribute")
        sub = row.row(align=True)
        sub.enabled = not scene_props.powera
        sub.prop(scene_props, "power", text="Power (S)", slider=True)

        layout.separator()

        # Custom G-code Section
        layout.prop(scene_props, "customize", text="Custom Start/End")
        if scene_props.customize:
            layout.prop(scene_props, "start_gcode", text="START")
            layout.prop(scene_props, "end_gcode", text="END")

        layout.operator("fabnodes.export_gcode", text="Export G-code")


# ---- Operator to Export G-code ----
class FABNODES_OT_ExportGCode(Operator):
    bl_idname = "fabnodes.export_gcode"
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
        if "position" in eval_obj.data.attributes:
            for pos in eval_obj.data.attributes["position"].data:
                global_pos = world_matrix @ pos.vector
                positions.append((global_pos.x * scale_factor, global_pos.y * scale_factor, global_pos.z * scale_factor))

        if not positions:
            self.report({"WARNING"}, "No valid positions found.")
            return {"CANCELLED"}

        # Attributes
        speeds = eval_obj.data.attributes.get("speed", None)
        extrudes = eval_obj.data.attributes.get("extrude", None)
        powers = eval_obj.data.attributes.get("power", None)

        speeds = speeds.data if speeds else [None] * len(positions)
        extrudes = extrudes.data if extrudes else [None] * len(positions)
        powers = powers.data if powers else [None] * len(positions)

        # Generate G-code
        for i, pos in enumerate(positions):
            speed_value = speeds[i].value if scene_props.speeda and speeds[i] else speed_global
            extrude_value = extrudes[i].value if scene_props.extrudea and extrudes[i] else extrude_global
            power_value = powers[i].value if scene_props.powera and powers[i] else power_global
            gcode_program.move_linear(*pos, speed=speed_value, extrude=extrude_value, power=power_value)

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

        self.report({"INFO"}, f"G-code saved as '{filename}'")
        return {"FINISHED"}


# ---- Registration ----
def register():
    bpy.utils.register_class(FABNODES_Properties)
    bpy.types.Scene.fabnodes_props = bpy.props.PointerProperty(type=FABNODES_Properties)
    bpy.utils.register_class(FABNODES_PT_ExporterPanel)
    bpy.utils.register_class(FABNODES_OT_ExportGCode)


def unregister():
    del bpy.types.Scene.fabnodes_props
    bpy.utils.unregister_class(FABNODES_OT_ExportGCode)
    bpy.utils.unregister_class(FABNODES_PT_ExporterPanel)
    bpy.utils.unregister_class(FABNODES_Properties)


if __name__ == "__main__":
    register()