# Fabnodes-GCode Exporter 🛠️

## 📌 Overview
**Fabnodes-GCode Exporter** is a Blender addon that allows you to export **geometry node toolpaths** as **G-code** for CNC machines, 3D printers, laser cutters, and pen plotters.

## 🚀 Features
- **Topology Slicer** (View3D > Sidebar > Fabnodes > Slicer):
  - Slicing strategies: **Planar**, **Geodesic** (equal surface distance), **Vase** (topological, between boundary loops), **Weight** (paint your own slicing field, Tissue-style).
  - Layer modes: fixed **Count** or **Height** (count derived from max layer height).
  - Toolpath-aware output: seam alignment, ping-pong direction for open curves, uniform resampling, CCW loops ordered bottom-to-top.
  - Slices the evaluated mesh (modifiers applied). Numpy-vectorized; uses scipy if installed.
  - Outputs `<object>_curves` for preview/editing, and **Make Toolpath Mesh** converts to `<object>_toolpath` — an ordered point mesh with `draw`/`path` attributes ready for the G-code exporter.
- Export Blender geometry node paths to **G-code (.nc files)**.
- Supports multiple machine modes:
  - 🛠 **CNC Mode**
  - 🖨 **3D Printing Mode**
  - ✍ **Drawing Mode**
  - 🔥 **Laser Cutting Mode**
- Customizable **feed rates, extrusion values, power settings**.
- Supports **custom start/end G-code**.

This addon is licensed under the GPL-3.0-or-later license.
Developer: Luis Pacheco
🌐 Website: luigipacheco.com

TO DO
 - Serial communication with CNC/3D printer
 - UI to connect/disconnect serial
 - Send custom G-Code commands
 - Jogging (manual movement) controls in UI

this project takes inspiration from other projects like g-code exporter by Alessandro zomparelli .