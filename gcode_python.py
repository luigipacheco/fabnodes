class GCode:
    def __init__(self, program_name="gcode_program", mode="cnc", pen_up_angle=250, pen_down_angle=0):
        self.program_name = program_name
        self.mode = mode  # Modes: "cnc", "3dp", "draw", "laser"
        self.commands = []
        self.pen_down = False  # Track pen state (for draw mode)
        self.pen_up_angle = pen_up_angle
        self.pen_down_angle = pen_down_angle
        self.start_program()

    def start_program(self):
        """Initializes the G-code program with default settings"""
        self.commands.append("G21 ; Set units to millimeters")
        self.commands.append("G90 ; Absolute positioning")
        
        if self.mode == "cnc":
            self.commands.append("G28 ; Home all axes")
        elif self.mode == "3dp":
            self.commands.append("M104 S200 ; Set extruder temperature")
            self.commands.append("M140 S60 ; Set bed temperature")
            self.commands.append("G28 ; Home all axes")
            self.commands.append("G92 E0 ; Reset extruder position")
        elif self.mode == "draw":
            self.set_pen_position(self.pen_up_angle)  # Start with the pen raised
        elif self.mode == "laser":
            self.commands.append("M3 ; Turn laser on")

    def set_speed(self, speed):
        """Sets feed rate"""
        self.commands.append(f"F{speed}")

    def move_linear(self, x, y, z, speed=None, extrude=None, power=None, draw=False):
        """Adds a linear move (G1) with optional drawing"""
        command = f"G1 X{x:.4f} Y{y:.4f} Z{z:.4f}" 
        if speed:
            command += f" F{speed}"

        if self.mode == "3dp" and extrude is not None:
            command += f" E{extrude}"
        elif self.mode == "laser" and power is not None:
            command += f" S{power}"
        elif self.mode == "cnc" and power is not None:
            command += f" S{power}"
        elif self.mode == "draw":
            if draw and not self.pen_down:
                self.set_pen_position(self.pen_down_angle)  # Lower pen
            elif not draw and self.pen_down:
                self.set_pen_position(self.pen_up_angle)  # Raise pen

        self.commands.append(command)

    def move_rapid(self, x, y, z):
        """Adds a rapid move (G0)"""
        self.commands.append(f"G0 X{x} Y{y} Z{z}")

    def set_pen_position(self, angle):
        """Moves the servo to control pen up/down dynamically"""
        command = f"M3 S{angle} ; {'Pen Down' if angle == self.pen_down_angle else 'Pen Up'}"
        self.commands.append(command)
        self.pen_down = (angle == self.pen_down_angle)  # Track pen state

    def set_spindle(self, speed):
        """Sets spindle speed (CNC)"""
        if self.mode == "cnc":
            self.commands.append(f"S{speed} M3 ; Start spindle")

    def stop_spindle(self):
        """Stops spindle or turns off laser"""
        if self.mode == "cnc":
            self.commands.append("M5 ; Stop spindle")
        elif self.mode == "laser":
            self.commands.append("M107 ; Turn laser off")

    def set_dwell(self, seconds):
        """Pauses the program for a given time"""
        self.commands.append(f"G4 P{seconds}")

    def end_program(self):
        """Ends the G-code program"""
        if self.mode == "3dp":
            self.commands.append("M104 S0 ; Turn off extruder")
            self.commands.append("M140 S0 ; Turn off bed")
        elif self.mode == "laser":
            self.commands.append("M5 S00 ; Ensure laser is off")
        elif self.mode == "draw":
            self.set_pen_position(self.pen_up_angle)  # Ensure pen is raised before stopping
        self.commands.append("M30 ; End of program")

    def save_program(self, filename="generated_gcode.nc"):
        """Saves the G-code program to a file"""
        with open(filename, 'w') as file:
            file.write('\n'.join(self.commands))
