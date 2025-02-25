# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Fabnodes-Gcode Export",
    "author" : "Luis Pacheco", 
    "description" : "Export geometry node toolpaths to  gcode",
    "blender" : (4, 0, 3),
    "version" : (0, 0, 1),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import bpy  # Import Blender Python API
from .gcode_python import GCode


addon_keymaps = {}
_icons = None
class SNA_PT_FABNODES_EXPORTER_FA98B(bpy.types.Panel):
    bl_label = 'Fabnodes Exporter'
    bl_idname = 'SNA_PT_FABNODES_EXPORTER_FA98B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Fabnodes'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        row_837BB = layout.row(heading='', align=False)
        row_837BB.alert = False
        row_837BB.enabled = True
        row_837BB.active = True
        row_837BB.use_property_split = False
        row_837BB.use_property_decorate = False
        row_837BB.scale_x = 1.0
        row_837BB.scale_y = 1.0
        row_837BB.alignment = 'Expand'.upper()
        row_837BB.operator_context = "INVOKE_DEFAULT" if False else "EXEC_DEFAULT"
        row_837BB.prop(bpy.context.scene, 'sna_mode', text='', icon_value=0, emboss=True)
        row_3ACA1 = layout.row(heading='', align=False)
        row_3ACA1.alert = False
        row_3ACA1.enabled = True
        row_3ACA1.active = True
        row_3ACA1.use_property_split = False
        row_3ACA1.use_property_decorate = False
        row_3ACA1.scale_x = 1.0
        row_3ACA1.scale_y = 1.0
        row_3ACA1.alignment = 'Expand'.upper()
        row_3ACA1.operator_context = "INVOKE_DEFAULT" if False else "EXEC_DEFAULT"
        row_3ACA1.prop(bpy.context.scene, 'sna_scale', text='export scale', icon_value=0, emboss=True)
        grid_3AE0E = layout.grid_flow(columns=3, row_major=False, even_columns=False, even_rows=False, align=False)
        grid_3AE0E.enabled = True
        grid_3AE0E.active = True
        grid_3AE0E.use_property_split = False
        grid_3AE0E.use_property_decorate = False
        grid_3AE0E.alignment = 'Expand'.upper()
        grid_3AE0E.scale_x = 1.0
        grid_3AE0E.scale_y = 1.0
        if not True: grid_3AE0E.operator_context = "EXEC_DEFAULT"
        grid_3AE0E.label(text='-', icon_value=0)
        grid_3AE0E.label(text='use attribute?', icon_value=0)
        grid_3AE0E.label(text='value', icon_value=0)
        grid_48A2B = layout.grid_flow(columns=3, row_major=False, even_columns=False, even_rows=False, align=False)
        grid_48A2B.enabled = True
        grid_48A2B.active = True
        grid_48A2B.use_property_split = False
        grid_48A2B.use_property_decorate = False
        grid_48A2B.alignment = 'Expand'.upper()
        grid_48A2B.scale_x = 1.0
        grid_48A2B.scale_y = 1.0
        if not True: grid_48A2B.operator_context = "EXEC_DEFAULT"
        grid_48A2B.label(text='speed (F)', icon_value=0)
        grid_48A2B.prop(bpy.context.scene, 'sna_speeda', text='', icon_value=0, emboss=True, invert_checkbox=True)
        grid_48A2B.prop(bpy.context.scene, 'sna_speed', text='', icon_value=0, emboss=bpy.context.scene.sna_speeda)
        grid_B9DAD = layout.grid_flow(columns=3, row_major=False, even_columns=False, even_rows=False, align=False)
        grid_B9DAD.enabled = True
        grid_B9DAD.active = True
        grid_B9DAD.use_property_split = False
        grid_B9DAD.use_property_decorate = False
        grid_B9DAD.alignment = 'Expand'.upper()
        grid_B9DAD.scale_x = 1.0
        grid_B9DAD.scale_y = 1.0
        if not True: grid_B9DAD.operator_context = "EXEC_DEFAULT"
        grid_B9DAD.label(text='extrude(E)', icon_value=0)
        grid_B9DAD.prop(bpy.context.scene, 'sna_extrudea', text='', icon_value=0, emboss=True, invert_checkbox=True)
        grid_B9DAD.prop(bpy.context.scene, 'sna_extrude', text='', icon_value=0, emboss=bpy.context.scene.sna_extrudea)
        grid_0ECE6 = layout.grid_flow(columns=3, row_major=False, even_columns=False, even_rows=False, align=False)
        grid_0ECE6.enabled = True
        grid_0ECE6.active = True
        grid_0ECE6.use_property_split = False
        grid_0ECE6.use_property_decorate = False
        grid_0ECE6.alignment = 'Expand'.upper()
        grid_0ECE6.scale_x = 1.0
        grid_0ECE6.scale_y = 1.0
        if not True: grid_0ECE6.operator_context = "EXEC_DEFAULT"
        grid_0ECE6.label(text='power(S)', icon_value=0)
        grid_0ECE6.prop(bpy.context.scene, 'sna_powera', text='', icon_value=0, emboss=True, invert_checkbox=True)
        grid_0ECE6.prop(bpy.context.scene, 'sna_power', text='', icon_value=0, emboss=bpy.context.scene.sna_powera)
        layout.prop(bpy.context.scene, 'sna_customize', text='Custom Start / End', icon_value=0, emboss=True)
        layout.prop_search(bpy.context.scene, 'sna_start', bpy.data, 'texts', text='START', icon='NONE')
        layout.prop_search(bpy.context.scene, 'sna_end', bpy.data, 'texts', text='END', icon='NONE')
        op = layout.operator('sna.export_gcode_450c9', text='export', icon_value=0, emboss=True, depress=False)


class SNA_OT_Export_Gcode_450C9(bpy.types.Operator):
    bl_idname = "sna.export_gcode_450c9"
    bl_label = "export gcode"
    bl_description = "export"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):

        def export_GCode():
            obj = bpy.context.object
            if not obj:
                print("No object selected.")
                return
            # Get object name for the filename
            filename = f"{obj.name}.nc"
            # Get custom properties from the scene
            mode = bpy.data.scenes['Scene'].sna_mode
            speed_global = bpy.data.scenes['Scene'].sna_speed
            extrude_global = bpy.data.scenes['Scene'].sna_extrude 
            power_global = bpy.data.scenes['Scene'].sna_power
            use_speed_global = not bpy.data.scenes['Scene'].sna_speeda
            use_extrude_global = not bpy.data.scenes['Scene'].sna_extrudea
            use_power_global = not bpy.data.scenes['Scene'].sna_powera
            use_custom_gcode = bpy.data.scenes['Scene'].sna_customize
            export_scale = bpy.data.scenes['Scene'].sna_scale
            # Get pen up/down angles for draw mode if applicable
            pen_up_angle = bpy.data.scenes['Scene'].get("sna_pen_up", 250)  # Default to 90
            pen_down_angle = bpy.data.scenes['Scene'].get("sna_pen_down", 0)  # Default to 0
            # Create GCode program with dynamic pen angles
            gcode_program = GCode(program_name=obj.name, mode=mode, pen_up_angle=pen_up_angle, pen_down_angle=pen_down_angle)
            # Override start G-code if customization is enabled
            if use_custom_gcode and "start" in bpy.data.texts:
                start_gcode = bpy.data.texts["start"].as_string()
                gcode_program.commands = start_gcode.split('\n')
            else:
                gcode_program.set_speed(speed_global)
            # Get world matrix (to transform local to global)
            world_matrix = obj.matrix_world
            scale = obj.scale
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            positions = []
            if "position" in eval_obj.data.attributes:
                for pos in eval_obj.data.attributes["position"].data:
                    local_pos = pos.vector  # Local coordinates
                    global_pos = world_matrix @ local_pos  # Convert to global space
                    # Apply object scale and convert to mm
                    x, y, z = global_pos.x * scale.x * export_scale, global_pos.y * scale.y * export_scale, global_pos.z * scale.z * export_scale  
                    positions.append((x, y, z))
            else:
                print("No position attribute found.")
                return
            if not positions:
                print("No valid positions found.")
                return
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
            # **Move through all points using G1**
            for i, pos in enumerate(positions):
                speed_value = speeds[i].value if (use_speed_global and speeds[i] and hasattr(speeds[i], 'value')) else speed_global
                extrude_value = extrudes[i].value if (use_extrude_global and extrudes[i] and hasattr(extrudes[i], 'value')) else extrude_global
                power_value = powers[i].value if (use_power_global and powers[i] and hasattr(powers[i], 'value')) else power_global
                draw_state = bool(draws[i].value) if (draws[i] and hasattr(draws[i], 'value')) else False  # Default to False
                gcode_program.move_linear(*pos, speed=speed_value, extrude=extrude_value, power=power_value, draw=draw_state)
                print(f"Moving to {pos} with speed={speed_value}, extrude={extrude_value}, power={power_value}, draw={draw_state}")
            # Override end G-code if customization is enabled
            if use_custom_gcode and "end" in bpy.data.texts:
                end_gcode = bpy.data.texts["end"].as_string()
                gcode_program.commands.extend(end_gcode.split('\n'))
            else:
                gcode_program.end_program()
            # Save as a Blender text block
            if filename in bpy.data.texts:
                bpy.data.texts[filename].clear()
            else:
                bpy.data.texts.new(filename)
            bpy.data.texts[filename].write('\n'.join(gcode_program.commands))
            print(f"GCode program saved as '{filename}' in Blender text editor.")
        # To test: Run export_GCode() when needed.
        export_GCode()
        return_44755 = export_GCode()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_sna_pt_fabnodes_exporter_c78f5_3BAFA(self, context):
    if not (False):
        layout = self.layout


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_mode = bpy.props.EnumProperty(name='mode', description='', items=[('cnc', 'cnc', '', 0, 0), ('3dp', '3dp', '', 0, 1), ('draw', 'draw', '', 0, 2), ('laser', 'laser', '', 0, 3)])
    bpy.types.Scene.sna_speed = bpy.props.FloatProperty(name='speed', description='', default=50.0, subtype='NONE', unit='NONE', step=100, precision=2)
    bpy.types.Scene.sna_power = bpy.props.FloatProperty(name='power', description='', default=50.0, subtype='NONE', unit='NONE', step=100, precision=2)
    bpy.types.Scene.sna_extrude = bpy.props.FloatProperty(name='extrude', description='', default=0.0, subtype='NONE', unit='NONE', step=100, precision=2)
    bpy.types.Scene.sna_speeda = bpy.props.BoolProperty(name='speeda', description='', default=False)
    bpy.types.Scene.sna_customize = bpy.props.BoolProperty(name='customize', description='', default=False)
    bpy.types.Scene.sna_extrudea = bpy.props.BoolProperty(name='extrudea', description='', default=False)
    bpy.types.Scene.sna_powera = bpy.props.BoolProperty(name='powera', description='', default=False)
    bpy.types.Scene.sna_start = bpy.props.PointerProperty(name='start', description='', type=bpy.types.Text)
    bpy.types.Scene.sna_end = bpy.props.PointerProperty(name='end', description='', type=bpy.types.Text)
    bpy.types.Scene.sna_scale = bpy.props.FloatProperty(name='scale', description='', default=1000.0, subtype='NONE', unit='NONE', step=100, precision=2)
    bpy.utils.register_class(SNA_PT_FABNODES_EXPORTER_FA98B)
    bpy.utils.register_class(SNA_OT_Export_Gcode_450C9)
    bpy.types.SNA_PT_FABNODES_EXPORTER_FA98B.append(sna_add_to_sna_pt_fabnodes_exporter_c78f5_3BAFA)



def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_scale
    del bpy.types.Scene.sna_end
    del bpy.types.Scene.sna_start
    del bpy.types.Scene.sna_powera
    del bpy.types.Scene.sna_extrudea
    del bpy.types.Scene.sna_customize
    del bpy.types.Scene.sna_speeda
    del bpy.types.Scene.sna_extrude
    del bpy.types.Scene.sna_power
    del bpy.types.Scene.sna_speed
    del bpy.types.Scene.sna_mode
    bpy.utils.unregister_class(SNA_PT_FABNODES_EXPORTER_FA98B)
    bpy.utils.unregister_class(SNA_OT_Export_Gcode_450C9)
    bpy.types.SNA_PT_FABNODES_EXPORTER_FA98B.remove(sna_add_to_sna_pt_fabnodes_exporter_c78f5_3BAFA)

