#!/usr/bin/env python3
"""
Game Object Editor - A tool to view and edit game objects (tiles, characters, etc.)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import toml
import json
from pathlib import Path
from PIL import Image, ImageTk
import os
import subprocess
import signal
import platform
import random
import math

class GameObjectEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Editor")
        self.root.geometry("1200x800")
        
        # Paths
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / "game_config.toml"
        self.assets_dir = self.project_root / "assets"
        self.current_sprite_sheet = "tiles.png"  # Default sprite sheet
        self.sprite_sheet_path = self.assets_dir / self.current_sprite_sheet
        
        # Data
        self.config = None
        self.current_object = None
        self.sprite_sheet_image = None
        self.sprite_sheet_photo = None
        self.original_sprite_image = None  # Original full-size image
        self.zoom_level = 1.0  # Current zoom level (1.0 = 100%)
        self.tile_size = 32  # Size of each tile in pixels
        self.server_process = None  # Reference to running server process
        
        # Create UI
        self.create_ui()
        
        # Load data
        self.load_config()
        self.refresh_sprite_sheets()  # Populate sprite sheet list
        self.load_sprite_sheet()  # Load default sprite sheet
        # Refresh tile palette after UI is created and config is loaded
        if hasattr(self, 'tile_palette_listbox'):
            self.refresh_tile_palette()
        
    def create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create Game Objects tab
        self.objects_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.objects_tab, text="Game Objects")
        
        # Create Map Editor tab
        self.map_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.map_tab, text="Map Editor")
        
        # Build Game Objects tab UI
        self.create_objects_tab_ui()
        
        # Build Map Editor tab UI
        self.create_map_tab_ui()
        
        # Bottom - Action buttons and status (shared across tabs)
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=1, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Restart Server", command=self.restart_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Shutdown Server", command=self.shutdown_server).pack(side=tk.LEFT, padx=5)
        self.server_status_label = ttk.Label(button_frame, text="Server: Unknown", foreground="gray")
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        # Status log area
        status_frame = ttk.LabelFrame(bottom_frame, text="Status", padding="5")
        status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.status_label = ttk.Label(status_frame, text="Ready", foreground="gray", wraplength=400)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Check server status on startup
        self.root.after(1000, self.check_server_status)
        
        # Status logging method
        self.log_status("Editor ready")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
    
    def create_objects_tab_ui(self):
        """Create the UI for the Game Objects tab"""
        # Left panel - Object list
        left_panel = ttk.Frame(self.objects_tab)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        ttk.Label(left_panel, text="Game Objects", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # Filter frame
        filter_frame = ttk.Frame(left_panel)
        filter_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self.filter_objects)
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=15)
        filter_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Object listbox with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.object_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, width=30)
        self.object_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.object_listbox.bind('<<ListboxSelect>>', self.on_object_select)
        scrollbar.config(command=self.object_listbox.yview)
        
        # Add/Delete buttons
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(button_frame, text="Add Object", command=self.add_object).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Delete", command=self.delete_object).pack(side=tk.LEFT)
        
        # Middle panel - Properties
        middle_panel = ttk.LabelFrame(self.objects_tab, text="Properties", padding="10")
        middle_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Define property schema: which properties each object type should show
        # Properties are: (label, key, dtype, always_show, show_for_types)
        self.property_schema = {
            "id": ("ID:", "id", str, True, []),  # Always show
            "name": ("Name:", "name", str, True, []),  # Always show
            "object_type": ("Type:", "object_type", str, True, []),  # Always show
            "walkable": ("Walkable:", "walkable", bool, False, ["tile"]),  # Only for tiles
            "health": ("Health:", "health", int, False, ["character", "item"]),  # For entities
            "attack": ("Attack:", "attack", int, False, ["character", "item"]),  # For entities
            "monster": ("Monster:", "monster", bool, False, ["character"]),  # Only for characters
            "healing_power": ("Healing Power:", "healing_power", int, False, ["consumable"]),  # Only for consumables
            "sprite_sheet": ("Sprite Sheet:", "sprite_sheet", str, True, []),  # Always show
        }
        
        # Properties form
        self.prop_vars = {}
        self.prop_widgets = {}  # Store widgets for showing/hiding
        self.prop_labels = {}  # Store labels for showing/hiding
        
        # Create all property fields (we'll show/hide them based on type)
        row = 0
        for key, (label, prop_key, dtype, always_show, show_for_types) in self.property_schema.items():
            # Label
            label_widget = ttk.Label(middle_panel, text=label)
            label_widget.grid(row=row, column=0, sticky=tk.W, pady=5)
            self.prop_labels[key] = label_widget
            
            # Input widget
            if dtype == bool:
                var = tk.BooleanVar()
                widget = ttk.Checkbutton(middle_panel, variable=var)
            elif dtype == int:
                var = tk.StringVar()
                widget = ttk.Entry(middle_panel, textvariable=var, width=20)
            else:
                var = tk.StringVar()
                widget = ttk.Entry(middle_panel, textvariable=var, width=20)
            
            widget.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
            self.prop_vars[key] = (var, dtype)
            self.prop_widgets[key] = widget
            
            # Add auto-save on field change
            if dtype == bool:
                var.trace_add("write", lambda *args, k=key: self._on_property_change(k))
            else:
                var.trace_add("write", lambda *args, k=key: self._on_property_change(k))
            
            row += 1
        
        # Type dropdown - special handling (replace the Entry widget with Combobox)
        # Remove the Entry widget that was created for object_type
        if "object_type" in self.prop_widgets:
            self.prop_widgets["object_type"].grid_remove()
        type_combo = ttk.Combobox(middle_panel, textvariable=self.prop_vars["object_type"][0], 
                                  values=["tile", "character", "item", "goal", "consumable"], width=17)
        type_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._on_object_type_changed())
        # Update the widget reference to point to the Combobox
        self.prop_widgets["object_type"] = type_combo
        
        # Sprite sheet dropdown (populated from available sprite sheets)
        # Find the correct row for sprite_sheet (it's the last property in schema)
        sprite_sheet_row = len(self.property_schema) - 1  # sprite_sheet is last
        # Remove the Entry widget that was created for sprite_sheet
        if "sprite_sheet" in self.prop_widgets:
            self.prop_widgets["sprite_sheet"].grid_remove()
        sprite_sheet_combo = ttk.Combobox(middle_panel, textvariable=self.prop_vars["sprite_sheet"][0], 
                                          width=17)
        sprite_sheet_combo.grid(row=sprite_sheet_row, column=1, sticky=(tk.W, tk.E), pady=5)
        # Update sprite sheet dropdown when sprite sheets are refreshed
        self.sprite_sheet_prop_combo = sprite_sheet_combo
        # Update the widget reference to point to the Combobox
        self.prop_widgets["sprite_sheet"] = sprite_sheet_combo
        
        # Store reference to middle_panel for dynamic row calculation
        self.middle_panel = middle_panel
        
        # Sprite array management
        sprite_row = len(self.property_schema)  # Use property_schema length instead
        ttk.Label(middle_panel, text="Sprites (for randomization):", font=("Arial", 10, "bold")).grid(
            row=sprite_row, column=0, columnspan=2, sticky=tk.W, pady=(20, 5))
        
        # Sprite list with scrollbar
        sprite_list_frame = ttk.Frame(middle_panel)
        sprite_list_frame.grid(row=sprite_row+1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        sprite_scrollbar = ttk.Scrollbar(sprite_list_frame)
        sprite_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sprite_listbox = tk.Listbox(sprite_list_frame, yscrollcommand=sprite_scrollbar.set, 
                                         height=4, width=30)
        self.sprite_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sprite_scrollbar.config(command=self.sprite_listbox.yview)
        
        # Sprite list buttons
        sprite_btn_frame = ttk.Frame(middle_panel)
        sprite_btn_frame.grid(row=sprite_row+2, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Button(sprite_btn_frame, text="Add from Click", command=self.add_sprite_from_click, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sprite_btn_frame, text="Remove Selected", command=self.remove_sprite, width=15).pack(side=tk.LEFT)
        
        # Custom properties
        ttk.Label(middle_panel, text="Custom Properties:", font=("Arial", 10, "bold")).grid(
            row=sprite_row+3, column=0, columnspan=2, sticky=tk.W, pady=(20, 5))
        
        self.custom_props_text = tk.Text(middle_panel, width=30, height=5)
        self.custom_props_text.grid(row=sprite_row+4, column=0, columnspan=2, 
                                    sticky=(tk.W, tk.E), pady=5)
        # Add auto-save on custom properties change
        self.custom_props_text.bind("<KeyRelease>", lambda e: self._on_property_change("properties"))
        
        # Note: Save is now handled by the main "Save" button at the bottom
        
        # Store last clicked coordinates for adding sprites
        self.last_clicked_sprite = None
        
        # Right panel - Sprite preview
        right_panel = ttk.LabelFrame(self.objects_tab, text="Sprite Preview", padding="10")
        right_panel.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas with scrollbars
        canvas_frame = ttk.Frame(right_panel)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.sprite_canvas = tk.Canvas(canvas_frame, width=400, height=400, bg="gray",
                                       yscrollcommand=v_scrollbar.set,
                                       xscrollcommand=h_scrollbar.set)
        self.sprite_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.sprite_canvas.yview)
        h_scrollbar.config(command=self.sprite_canvas.xview)
        
        # Sprite sheet selection
        sheet_frame = ttk.Frame(right_panel)
        sheet_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(sheet_frame, text="Sprite Sheet:").pack(side=tk.LEFT, padx=(0, 5))
        self.sprite_sheet_var = tk.StringVar()
        self.sprite_sheet_combo = ttk.Combobox(sheet_frame, textvariable=self.sprite_sheet_var, 
                                                state="readonly", width=30)
        self.sprite_sheet_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.sprite_sheet_combo.bind("<<ComboboxSelected>>", self.on_sprite_sheet_change)
        ttk.Button(sheet_frame, text="Refresh", command=self.refresh_sprite_sheets, width=8).pack(side=tk.LEFT)
        
        # Sprite sheet navigation and zoom controls
        nav_frame = ttk.Frame(right_panel)
        nav_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(nav_frame, text="Click on sprite sheet to set coordinates").pack()
        
        # Zoom controls
        zoom_frame = ttk.Frame(nav_frame)
        zoom_frame.pack(pady=(5, 0))
        ttk.Button(zoom_frame, text="Zoom In (+)", command=self.zoom_in, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom Out (-)", command=self.zoom_out, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Reset (1x)", command=self.zoom_reset, width=12).pack(side=tk.LEFT, padx=2)
        self.zoom_label = ttk.Label(zoom_frame, text="Zoom: 100%")
        self.zoom_label.pack(side=tk.LEFT, padx=(10, 0))
        
        self.sprite_canvas.bind("<Button-1>", self.on_sprite_click)
        # Mouse wheel support (different on different platforms)
        self.sprite_canvas.bind("<MouseWheel>", self.on_mousewheel)  # Windows/Linux
        self.sprite_canvas.bind("<Button-4>", lambda e: self.zoom_in())  # macOS scroll up
        self.sprite_canvas.bind("<Button-5>", lambda e: self.zoom_out())  # macOS scroll down
        # Make canvas focusable for mouse wheel
        self.sprite_canvas.bind("<Enter>", lambda e: self.sprite_canvas.focus_set())
        self.sprite_canvas.bind("<Leave>", lambda e: self.root.focus_set())
        
        # Configure grid weights for objects tab
        self.objects_tab.columnconfigure(1, weight=1)
        self.objects_tab.rowconfigure(0, weight=1)
    
    def create_map_tab_ui(self):
        """Create the UI for the Map Editor tab"""
        # Left panel - Tile palette
        left_panel = ttk.LabelFrame(self.map_tab, text="Tile Palette", padding="10")
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        ttk.Label(left_panel, text="Select a tile to place:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Tile list with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tile_palette_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, width=25)
        self.tile_palette_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tile_palette_listbox.bind('<<ListboxSelect>>', self.on_tile_palette_select)
        scrollbar.config(command=self.tile_palette_listbox.yview)
        
        # Map controls
        controls_frame = ttk.LabelFrame(self.map_tab, text="Map Controls", padding="10")
        controls_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        ttk.Button(controls_frame, text="Generate Procedural Map", command=self.generate_procedural_map, 
                  style="Accent.TButton").pack(fill=tk.X, pady=5)
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(controls_frame, text="Map Preview Only", font=("Arial", 9), foreground="gray").pack(pady=5)
        
        # Map info
        info_frame = ttk.LabelFrame(controls_frame, text="Map Info", padding="5")
        info_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Label(info_frame, text="Width:").pack(anchor=tk.W)
        self.map_width_var = tk.StringVar(value="80")
        ttk.Entry(info_frame, textvariable=self.map_width_var, width=15).pack(fill=tk.X, pady=2)
        
        ttk.Label(info_frame, text="Height:").pack(anchor=tk.W, pady=(10, 0))
        self.map_height_var = tk.StringVar(value="50")
        ttk.Entry(info_frame, textvariable=self.map_height_var, width=15).pack(fill=tk.X, pady=2)
        
        # Right panel - Map canvas
        right_panel = ttk.LabelFrame(self.map_tab, text="Map", padding="10")
        right_panel.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas with scrollbars for map
        canvas_frame = ttk.Frame(right_panel)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.map_canvas = tk.Canvas(canvas_frame, width=600, height=600, bg="black",
                                    yscrollcommand=v_scrollbar.set,
                                    xscrollcommand=h_scrollbar.set)
        self.map_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.map_canvas.yview)
        h_scrollbar.config(command=self.map_canvas.xview)
        
        # Map zoom controls
        zoom_frame = ttk.Frame(right_panel)
        zoom_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(zoom_frame, text="Zoom In (+)", command=self.map_zoom_in, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom Out (-)", command=self.map_zoom_out, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Reset (1x)", command=self.map_zoom_reset, width=12).pack(side=tk.LEFT, padx=2)
        self.map_zoom_label = ttk.Label(zoom_frame, text="Zoom: 100%")
        self.map_zoom_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Map canvas mouse wheel support for zoom
        self.map_canvas.bind("<MouseWheel>", self.on_map_mousewheel)  # Windows/Linux
        self.map_canvas.bind("<Button-4>", lambda e: self.map_zoom_in())  # macOS scroll up
        self.map_canvas.bind("<Button-5>", lambda e: self.map_zoom_out())  # macOS scroll down
        # Make canvas focusable for mouse wheel
        self.map_canvas.bind("<Enter>", lambda e: self.map_canvas.focus_set())
        self.map_canvas.bind("<Leave>", lambda e: self.root.focus_set())
        
        # Map data
        self.map_data = None  # Will be a 2D list of tile IDs
        self.map_width = 80
        self.map_height = 50
        self.selected_tile_id = None
        self.map_entities = []  # List of entities (monsters) on the map: [(x, y, object_id), ...]
        self.map_rooms = []  # List of rooms: [(x, y, width, height), ...]
        self.map_zoom_level = 1.0  # Zoom level for map (1.0 = 100%)
        self.map_stairs_position = None  # Position of stairs (goal)
        
        # Configure grid weights for map tab
        self.map_tab.columnconfigure(2, weight=1)
        self.map_tab.rowconfigure(0, weight=1)
    
    def log_status(self, message, level="info"):
        """Log a status message to the status label"""
        colors = {
            "info": "black",
            "success": "green",
            "warning": "orange",
            "error": "red"
        }
        color = colors.get(level, "black")
        self.status_label.config(text=message, foreground=color)
        # Auto-clear success messages after 3 seconds
        if level == "success":
            self.root.after(3000, lambda: self.log_status("Ready", "info"))
    
    def _on_object_type_changed(self):
        """Update property visibility when object type changes"""
        if not self.current_object:
            return
        
        # Get current object type
        obj_type = self.prop_vars["object_type"][0].get()
        if not obj_type:
            return
        
        # Update property visibility
        self._update_property_visibility(obj_type)
    
    def _update_property_visibility(self, obj_type):
        """Show/hide properties based on object type"""
        for key, (label, prop_key, dtype, always_show, show_for_types) in self.property_schema.items():
            should_show = always_show or (obj_type in show_for_types)
            
            if key in self.prop_labels and key in self.prop_widgets:
                if should_show:
                    self.prop_labels[key].grid()
                    self.prop_widgets[key].grid()
                else:
                    self.prop_labels[key].grid_remove()
                    self.prop_widgets[key].grid_remove()
    
    def _on_property_change(self, key):
        """Handle property change - auto-save after a short delay"""
        if not self.current_object:
            return
        # Don't auto-save when loading object into form (would cause infinite loop)
        if hasattr(self, '_loading_object') and self._loading_object:
            return
        # Debounce: cancel previous auto-save and schedule a new one
        if hasattr(self, '_auto_save_job'):
            self.root.after_cancel(self._auto_save_job)
        # Auto-save after 500ms of no changes
        self._auto_save_job = self.root.after(500, self._auto_save_object)
    
    def _auto_save_object(self):
        """Auto-save current object changes"""
        if self.current_object:
            try:
                self._save_current_object_changes()
            except Exception as e:
                # Don't show error for auto-save, just log it
                print(f"Auto-save error: {e}")
    
    def load_config(self):
        """Load game config from TOML file"""
        if not self.config_path.exists():
            self.log_status(f"Config file not found. Creating default config.", "warning")
            self.config = {"game_objects": []}
            self.save_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = toml.load(f)
            
            # Check if config is empty or has no game_objects
            if not self.config or "game_objects" not in self.config or len(self.config.get("game_objects", [])) == 0:
                response = messagebox.askyesno(
                    "Empty Config",
                    "The config file is empty or has no game objects.\n\n"
                    "Would you like to create default game objects?\n"
                    "(Yes = Create defaults, No = Keep empty)"
                )
                if response:
                    self.create_default_objects()
                    self.save_config()
            
            self.refresh_object_list()
            # Refresh tile palette if UI is already created
            if hasattr(self, 'tile_palette_listbox'):
                self.refresh_tile_palette()
            self.log_status(f"Loaded {len(self.config.get('game_objects', []))} game objects", "success")
        except Exception as e:
            self.log_status(f"Failed to load config: {e}", "error")
            self.config = {"game_objects": []}
    
    def create_default_objects(self):
        """Create default game objects"""
        self.config = {
            "game_objects": [
                {
                    "id": "wall_dirt_top",
                    "name": "Dirt Wall (Top)",
                    "object_type": "tile",
                    "walkable": False,
                    "sprite_x": 0,
                    "sprite_y": 0,
                    "sprites": [{"x": 0, "y": 0}],
                    "properties": {}
                },
                {
                    "id": "wall_dirt_side",
                    "name": "Dirt Wall (Side)",
                    "object_type": "tile",
                    "walkable": False,
                    "sprite_x": 1,
                    "sprite_y": 0,
                    "sprites": [{"x": 1, "y": 0}],
                    "properties": {}
                },
                {
                    "id": "wall_stone_top",
                    "name": "Stone Wall (Top)",
                    "object_type": "tile",
                    "walkable": False,
                    "sprite_x": 0,
                    "sprite_y": 1,
                    "sprites": [{"x": 0, "y": 1}],
                    "properties": {}
                },
                {
                    "id": "floor_dark",
                    "name": "Dark Floor",
                    "object_type": "tile",
                    "walkable": True,
                    "sprite_x": 0,
                    "sprite_y": 6,
                    "sprites": [{"x": 0, "y": 6}],
                    "properties": {}
                },
                {
                    "id": "floor_stone",
                    "name": "Stone Floor",
                    "object_type": "tile",
                    "walkable": True,
                    "sprite_x": 1,
                    "sprite_y": 6,
                    "sprites": [
                        {"x": 1, "y": 6},
                        {"x": 2, "y": 6},
                        {"x": 3, "y": 6}
                    ],
                    "properties": {}
                },
                {
                    "id": "player",
                    "name": "Player Character",
                    "object_type": "character",
                    "walkable": True,
                    "health": 100,
                    "sprite_x": 0,
                    "sprite_y": 0,
                    "sprites": [{"x": 0, "y": 0}],
                    "properties": {}
                }
            ]
        }
    
    def refresh_sprite_sheets(self):
        """Refresh the list of available sprite sheets"""
        sprite_sheets = []
        if self.assets_dir.exists():
            # Find all PNG files in assets directory
            for file in self.assets_dir.glob("*.png"):
                sprite_sheets.append(file.name)
        
        # Sort alphabetically
        sprite_sheets.sort()
        
        # Update preview combobox
        if hasattr(self, 'sprite_sheet_combo'):
            self.sprite_sheet_combo['values'] = sprite_sheets
            
            # Set current selection if it exists, otherwise use first one
            if sprite_sheets:
                if self.current_sprite_sheet in sprite_sheets:
                    self.sprite_sheet_var.set(self.current_sprite_sheet)
                else:
                    self.current_sprite_sheet = sprite_sheets[0]
                    self.sprite_sheet_var.set(self.current_sprite_sheet)
            else:
                self.sprite_sheet_var.set("")
        
        # Update property combobox if it exists
        if hasattr(self, 'sprite_sheet_prop_combo'):
            self.sprite_sheet_prop_combo['values'] = sprite_sheets
    
    def on_sprite_sheet_change(self, event=None):
        """Handle sprite sheet selection change"""
        new_sheet = self.sprite_sheet_var.get()
        if new_sheet and new_sheet != self.current_sprite_sheet:
            # Clear any existing highlights before switching
            self.sprite_canvas.delete("highlight")
            
            self.current_sprite_sheet = new_sheet
            self.sprite_sheet_path = self.assets_dir / self.current_sprite_sheet
            self.load_sprite_sheet()
            
            # Only highlight if the current object uses this sprite sheet
            if self.current_object:
                obj_sprite_sheet = self.current_object.get("sprite_sheet")
                if obj_sprite_sheet == self.current_sprite_sheet:
                    self.highlight_sprite()
                else:
                    # Clear highlight if object uses a different sprite sheet
                    self.sprite_canvas.delete("highlight")
    
    def load_sprite_sheet(self):
        """Load sprite sheet image"""
        if not self.sprite_sheet_path.exists():
            self.log_status(f"Sprite sheet not found: {self.sprite_sheet_path}", "error")
            return
        
        try:
            # Load original image (don't resize)
            self.original_sprite_image = Image.open(self.sprite_sheet_path)
            self.zoom_level = 1.0
            self.update_sprite_display()
            self.log_status(f"Loaded sprite sheet: {self.current_sprite_sheet}", "success")
        except Exception as e:
            self.log_status(f"Failed to load sprite sheet: {e}", "error")
    
    def update_sprite_display(self):
        """Update the sprite sheet display with current zoom level"""
        if not self.original_sprite_image:
            return
        
        # Calculate new size based on zoom
        new_width = int(self.original_sprite_image.width * self.zoom_level)
        new_height = int(self.original_sprite_image.height * self.zoom_level)
        
        # Resize image
        self.sprite_sheet_image = self.original_sprite_image.resize(
            (new_width, new_height), 
            Image.Resampling.LANCZOS
        )
        self.sprite_sheet_photo = ImageTk.PhotoImage(self.sprite_sheet_image)
        
        # Clear canvas and redraw
        self.sprite_canvas.delete("all")
        self.sprite_canvas.create_image(0, 0, anchor=tk.NW, image=self.sprite_sheet_photo)
        self.sprite_canvas.config(scrollregion=self.sprite_canvas.bbox("all"))
        
        # Update zoom label
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")
        
        # Redraw highlight if object is selected and uses this sprite sheet
        if self.current_object:
            self.highlight_sprite()  # highlight_sprite now checks sprite sheet match internally
    
    def zoom_in(self):
        """Zoom in on sprite sheet"""
        self.zoom_level = min(self.zoom_level * 1.5, 8.0)  # Max 8x zoom
        self.update_sprite_display()
    
    def zoom_out(self):
        """Zoom out on sprite sheet"""
        self.zoom_level = max(self.zoom_level / 1.5, 0.25)  # Min 0.25x zoom
        self.update_sprite_display()
    
    def zoom_reset(self):
        """Reset zoom to 100%"""
        self.zoom_level = 1.0
        self.update_sprite_display()
    
    def on_mousewheel(self, event):
        """Handle mouse wheel for zooming"""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
    
    # Map zoom methods
    def map_zoom_in(self):
        """Zoom in on map"""
        self.map_zoom_level = min(self.map_zoom_level * 1.5, 8.0)  # Max 8x zoom
        self.update_map_zoom_display()
        self.render_map()
    
    def map_zoom_out(self):
        """Zoom out on map"""
        self.map_zoom_level = max(self.map_zoom_level / 1.5, 0.25)  # Min 0.25x zoom
        self.update_map_zoom_display()
        self.render_map()
    
    def map_zoom_reset(self):
        """Reset map zoom to 100%"""
        self.map_zoom_level = 1.0
        self.update_map_zoom_display()
        self.render_map()
    
    def on_map_mousewheel(self, event):
        """Handle mouse wheel for map zoom"""
        if event.delta > 0:
            self.map_zoom_in()
        else:
            self.map_zoom_out()
    
    def update_map_zoom_display(self):
        """Update the map zoom label"""
        if hasattr(self, 'map_zoom_label'):
            self.map_zoom_label.config(text=f"Zoom: {int(self.map_zoom_level * 100)}%")
    
    def refresh_object_list(self, preserve_selection=False):
        """Refresh the object listbox
        
        Args:
            preserve_selection: If True, restore the selection after refresh
        """
        # Save current selection if preserving
        selected_id = None
        if preserve_selection and self.current_object:
            selected_id = self.current_object.get("id")
        
        self.object_listbox.delete(0, tk.END)
        if not self.config or "game_objects" not in self.config:
            return
        
        filter_text = self.filter_var.get().lower()
        for idx, obj in enumerate(self.config["game_objects"]):
            name = obj.get("name", obj.get("id", "Unknown"))
            obj_type = obj.get("object_type", "unknown")
            display_text = f"{name} ({obj_type})"
            if filter_text == "" or filter_text in display_text.lower():
                listbox_idx = self.object_listbox.size()
                self.object_listbox.insert(tk.END, display_text)
                # Restore selection if this is the selected object
                if preserve_selection and selected_id and obj.get("id") == selected_id:
                    self.object_listbox.selection_set(listbox_idx)
                    self.object_listbox.see(listbox_idx)
    
    def filter_objects(self, *args):
        """Filter objects based on search text"""
        self.refresh_object_list()
    
    def on_object_select(self, event):
        """Handle object selection"""
        selection = self.object_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        filter_text = self.filter_var.get().lower()
        
        # Find actual index in config
        if filter_text:
            filtered = [i for i, obj in enumerate(self.config["game_objects"])
                       if filter_text in f"{obj.get('name', obj.get('id', ''))} ({obj.get('object_type', '')})".lower()]
            if idx < len(filtered):
                actual_idx = filtered[idx]
            else:
                return
        else:
            actual_idx = idx
        
        if actual_idx < len(self.config["game_objects"]):
            self.current_object = self.config["game_objects"][actual_idx]
            # Switch to object's sprite sheet if specified
            obj_sprite_sheet = self.current_object.get("sprite_sheet")
            if obj_sprite_sheet and obj_sprite_sheet != self.current_sprite_sheet:
                if obj_sprite_sheet in self.sprite_sheet_combo['values']:
                    self.sprite_sheet_var.set(obj_sprite_sheet)
                    self.on_sprite_sheet_change()
            self.load_object_to_form()
            self.highlight_sprite()
    
    def load_object_to_form(self):
        """Load current object properties into form"""
        if not self.current_object:
            return
        
        # Set flag to prevent auto-save during loading
        self._loading_object = True
        
        obj = self.current_object
        
        # Get object type and update property visibility
        obj_type = obj.get("object_type", "tile")
        self._update_property_visibility(obj_type)
        
        # Set standard properties
        for key, (var, dtype) in self.prop_vars.items():
            if key in obj:
                if dtype == bool:
                    var.set(obj[key])
                elif dtype == int:
                    var.set(str(obj.get(key, "")))
                else:
                    # For string fields like sprite_sheet, preserve the value
                    var.set(str(obj.get(key, "")))
            else:
                if dtype == bool:
                    # For monster checkbox, check both top-level and properties map as fallback
                    if key == "monster":
                        # Check both top-level and properties map
                        monster_val = obj.get("monster")
                        if monster_val is None:
                            monster_val = obj.get("properties", {}).get("monster", False)
                            # Handle string "true"/"false" from properties
                            if isinstance(monster_val, str):
                                monster_val = monster_val.lower() == "true"
                        var.set(bool(monster_val))
                    else:
                        var.set(False)
                else:
                    # Don't clear string fields - they might have values we want to preserve
                    var.set("")
        
        # Handle health (can be None)
        health = obj.get("health")
        if health is None:
            self.prop_vars["health"][0].set("")
        else:
            self.prop_vars["health"][0].set(str(health))
        
        # Load sprite array
        self.sprite_listbox.delete(0, tk.END)
        sprites = obj.get("sprites", [])
        # If no sprites array, check for legacy sprite_x/sprite_y
        if not sprites:
            sprite_x = obj.get("sprite_x")
            sprite_y = obj.get("sprite_y")
            if sprite_x is not None and sprite_y is not None:
                sprites = [{"x": sprite_x, "y": sprite_y}]
        
        for sprite in sprites:
            x = sprite.get("x", 0) if isinstance(sprite, dict) else sprite.x if hasattr(sprite, 'x') else 0
            y = sprite.get("y", 0) if isinstance(sprite, dict) else sprite.y if hasattr(sprite, 'y') else 0
            self.sprite_listbox.insert(tk.END, f"({x}, {y})")
        
        # Load custom properties
        props = obj.get("properties", {})
        props_text = "\n".join(f"{k}={v}" for k, v in props.items())
        self.custom_props_text.delete(1.0, tk.END)
        self.custom_props_text.insert(1.0, props_text)
        
        # Clear loading flag - done loading object into form
        self._loading_object = False
    
    
    def add_sprite_from_click(self):
        """Add sprite from last click or prompt for coordinates"""
        if not self.current_object:
            self.log_status("Please select an object first", "warning")
            return
        
        if self.last_clicked_sprite:
            x, y = self.last_clicked_sprite
            self.sprite_listbox.insert(tk.END, f"({x}, {y})")
            self.last_clicked_sprite = None
            # Auto-save after adding sprite
            if self.current_object:
                self._save_current_object_changes()
        else:
            # Prompt for coordinates
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Sprite")
            dialog.geometry("300x120")
            
            ttk.Label(dialog, text="X coordinate:").grid(row=0, column=0, padx=10, pady=10)
            x_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=x_var, width=10).grid(row=0, column=1, padx=10, pady=10)
            
            ttk.Label(dialog, text="Y coordinate:").grid(row=1, column=0, padx=10, pady=10)
            y_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=y_var, width=10).grid(row=1, column=1, padx=10, pady=10)
            
            def add_sprite():
                try:
                    x = int(x_var.get())
                    y = int(y_var.get())
                    self.sprite_listbox.insert(tk.END, f"({x}, {y})")
                    dialog.destroy()
                    # Auto-save after adding sprite
                    if self.current_object:
                        self._save_current_object_changes()
                except ValueError:
                    self.log_status("Please enter valid numbers", "error")
            
            ttk.Button(dialog, text="Add", command=add_sprite).grid(row=2, column=0, columnspan=2, pady=10)
    
    def remove_sprite(self):
        """Remove selected sprite from list"""
        selection = self.sprite_listbox.curselection()
        if selection:
            index = selection[0]
            self.sprite_listbox.delete(index)
            # Update the object's sprites array immediately from listbox
            if self.current_object:
                # Set flag to prevent auto-save from reloading form
                self._loading_object = True
                # Update sprites array from listbox
                sprites = []
                for i in range(self.sprite_listbox.size()):
                    text = self.sprite_listbox.get(i)
                    # Parse "(x, y)" format
                    import re
                    match = re.match(r'\((\d+),\s*(\d+)\)', text)
                    if match:
                        sprites.append({"x": int(match.group(1)), "y": int(match.group(2))})
                # Update the object's sprites array directly
                self.current_object["sprites"] = sprites
                # Remove legacy fields if sprites array exists
                if sprites and len(sprites) > 0:
                    self.current_object.pop("sprite_x", None)
                    self.current_object.pop("sprite_y", None)
                else:
                    # If no sprites left, ensure we have an empty array
                    self.current_object["sprites"] = []
                self._loading_object = False
                # Save config directly without calling _save_current_object_changes
                # (which might trigger a reload)
                self.save_config()
                self.log_status("Sprite removed", "success")
    
    def add_object(self):
        """Add a new game object"""
        new_obj = {
            "id": f"new_object_{len(self.config.get('game_objects', []))}",
            "name": "New Object",
            "object_type": "tile",
            "walkable": False,
            "health": None,
            "sprites": [{"x": 0, "y": 0}],
            "properties": {}
        }
        
        if "game_objects" not in self.config:
            self.config["game_objects"] = []
        
        self.config["game_objects"].append(new_obj)
        self.current_object = new_obj
        self.load_object_to_form()
        self.refresh_object_list()
        # Refresh tile palette if it exists
        if hasattr(self, 'tile_palette_listbox'):
            self.refresh_tile_palette()
        # Select the new object
        self.object_listbox.selection_set(len(self.config["game_objects"]) - 1)
        self.object_listbox.see(len(self.config["game_objects"]) - 1)
        # Auto-save after adding object
        self.save_config(show_message=True)
        self.log_status("New object added", "success")
    
    def delete_object(self):
        """Delete selected object"""
        if not self.current_object:
            self.log_status("Please select an object to delete", "warning")
            return
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this object?"):
            if self.current_object in self.config["game_objects"]:
                self.config["game_objects"].remove(self.current_object)
                self.current_object = None
                self.refresh_object_list()
                # Refresh tile palette if it exists
                if hasattr(self, 'tile_palette_listbox'):
                    self.refresh_tile_palette()
                # Clear form
                for var, _ in self.prop_vars.values():
                    if isinstance(var, tk.BooleanVar):
                        var.set(False)
                    else:
                        var.set("")
                self.custom_props_text.delete(1.0, tk.END)
                self.sprite_listbox.delete(0, tk.END)
                # Automatically save to clean up the file
                self.save_config(show_message=True)
                self.log_status("Object deleted", "success")
    
    def highlight_sprite(self):
        """Highlight all sprites in the array on the sprite sheet"""
        if not self.current_object or not self.sprite_sheet_image:
            return
        
        # Clear previous highlights
        self.sprite_canvas.delete("highlight")
        
        # Only highlight if the object's sprite_sheet matches the current sprite sheet
        obj_sprite_sheet = self.current_object.get("sprite_sheet")
        if obj_sprite_sheet and obj_sprite_sheet != self.current_sprite_sheet:
            # Object uses a different sprite sheet, don't highlight
            return
        
        # Get sprites array
        sprites = self.current_object.get("sprites", [])
        # If no sprites array, check for legacy sprite_x/sprite_y
        if not sprites:
            sprite_x = self.current_object.get("sprite_x")
            sprite_y = self.current_object.get("sprite_y")
            if sprite_x is not None and sprite_y is not None:
                sprites = [{"x": sprite_x, "y": sprite_y}]
        
        if not sprites:
            return
        
        # Calculate position based on tile coordinates and zoom
        scaled_tile_size = self.tile_size * self.zoom_level
        
        # Highlight all sprites in the array
        for i, sprite in enumerate(sprites):
            x_coord = sprite.get("x", 0) if isinstance(sprite, dict) else sprite.x if hasattr(sprite, 'x') else 0
            y_coord = sprite.get("y", 0) if isinstance(sprite, dict) else sprite.y if hasattr(sprite, 'y') else 0
            
            x = x_coord * scaled_tile_size
            y = y_coord * scaled_tile_size
            
            # Use different colors for multiple sprites
            color = "red" if i == 0 else "orange"
            width = max(2, int(2 * self.zoom_level))
            
            # Draw highlight rectangle
            self.sprite_canvas.create_rectangle(
                x, y, x + scaled_tile_size, y + scaled_tile_size,
                outline=color, width=width, tags="highlight"
            )
    
    def on_sprite_click(self, event):
        """Handle click on sprite sheet to set coordinates"""
        if not self.current_object:
            self.log_status("Please select a game object first", "warning")
            return
        
        if not self.sprite_sheet_image:
            return
        
        # Get canvas coordinates (accounting for scrolling)
        canvas_x = self.sprite_canvas.canvasx(event.x)
        canvas_y = self.sprite_canvas.canvasy(event.y)
        
        # Calculate tile coordinates based on zoom level
        scaled_tile_size = self.tile_size * self.zoom_level
        tile_x = int(canvas_x / scaled_tile_size)
        tile_y = int(canvas_y / scaled_tile_size)
        
        # Ensure coordinates are valid
        if tile_x < 0 or tile_y < 0:
            return
        
        # Calculate max valid coordinates based on original image size
        max_tiles_x = self.original_sprite_image.width // self.tile_size
        max_tiles_y = self.original_sprite_image.height // self.tile_size
        
        if tile_x >= max_tiles_x or tile_y >= max_tiles_y:
            self.log_status(f"Coordinates ({tile_x}, {tile_y}) are outside bounds (max: {max_tiles_x-1}, {max_tiles_y-1})", "warning")
            return
        
        # Store clicked coordinates for adding to sprite array
        self.last_clicked_sprite = (tile_x, tile_y)
        
        # Ask if user wants to add or replace
        response = messagebox.askyesnocancel(
            "Add Sprite",
            f"Add sprite ({tile_x}, {tile_y}) to sprite array?\n\n"
            "Yes = Add to array\n"
            "No = Replace all sprites\n"
            "Cancel = Do nothing"
        )
        
        if response is True:
            # Add to array
            sprites = self.current_object.get("sprites", [])
            sprites.append({"x": tile_x, "y": tile_y})
            self.current_object["sprites"] = sprites
            # Automatically set sprite_sheet property to current sheet
            self.current_object["sprite_sheet"] = self.current_sprite_sheet
            self.load_object_to_form()  # Refresh the form
            # Auto-save after adding sprite
            self._save_current_object_changes()
        elif response is False:
            # Replace all sprites
            self.current_object["sprites"] = [{"x": tile_x, "y": tile_y}]
            # Automatically set sprite_sheet property to current sheet
            self.current_object["sprite_sheet"] = self.current_sprite_sheet
            self.load_object_to_form()  # Refresh the form
            # Auto-save after replacing sprites
            self._save_current_object_changes()
        
        # Redraw highlight
        self.highlight_sprite()
        
        # Show feedback
        if response is not None:
            print(f"✓ {'Added' if response else 'Set'} sprite coordinates ({tile_x}, {tile_y}) for '{self.current_object.get('name', 'object')}'")
    
    def save_all(self):
        """Save current object changes and then save config to file (auto-save)"""
        # First, save current object changes if an object is selected
        if self.current_object:
            try:
                self._save_current_object_changes()
            except Exception as e:
                self.log_status(f"Failed to save object changes: {e}", "error")
                return
        
        # Then save the config file
        self.save_config()
    
    def _save_current_object_changes(self):
        """Save current object changes to memory (internal method)"""
        if not self.current_object:
            return
        
        # Update properties
        for key, (var, dtype) in self.prop_vars.items():
            if key == "health":
                val = var.get()
                self.current_object["health"] = int(val) if val.strip() else None
            elif key == "attack":
                val = var.get()
                # Store attack as top-level property (not in properties map)
                self.current_object["attack"] = int(val) if val.strip() else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "attack" in self.current_object["properties"]:
                    del self.current_object["properties"]["attack"]
            elif key == "sprite_sheet":
                val = var.get().strip()
                if val:
                    self.current_object["sprite_sheet"] = val
                    # Switch to this sprite sheet if it's different
                    if val != self.current_sprite_sheet and val in self.sprite_sheet_combo['values']:
                        self.sprite_sheet_var.set(val)
                        self.on_sprite_sheet_change()
                # Don't remove sprite_sheet if it exists - preserve it even if form field is empty
                # Only update if a new value is provided
            elif key == "monster":
                # Store monster as top-level boolean property (not in properties map)
                self.current_object["monster"] = var.get()
                # Remove from properties map if it was there
                if "properties" in self.current_object and "monster" in self.current_object["properties"]:
                    del self.current_object["properties"]["monster"]
            elif dtype == bool:
                self.current_object[key] = var.get()
            elif dtype == int:
                self.current_object[key] = int(var.get() or "0")
            else:
                self.current_object[key] = var.get()
        
        # Update sprite array from listbox
        sprites = []
        for i in range(self.sprite_listbox.size()):
            text = self.sprite_listbox.get(i)
            # Parse "(x, y)" format
            import re
            match = re.match(r'\((\d+),\s*(\d+)\)', text)
            if match:
                sprites.append({"x": int(match.group(1)), "y": int(match.group(2))})
        self.current_object["sprites"] = sprites
        
        # Remove legacy fields if sprites array exists and has items
        if sprites and len(sprites) > 0:
            self.current_object.pop("sprite_x", None)
            self.current_object.pop("sprite_y", None)
        
        # Preserve sprite_sheet if it exists - don't remove it
        # It will be updated by the form field if changed, but won't be removed
        
        # Update custom properties
        props_text = self.custom_props_text.get(1.0, tk.END).strip()
        props = {}
        if props_text:
            for line in props_text.split("\n"):
                line = line.strip()
                if line and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
        self.current_object["properties"] = props if props else {}
        
        # Refresh the object list to show updated name (preserve selection)
        # Only refresh if we're not in the middle of loading (to avoid reloading sprites)
        if not getattr(self, '_loading_object', False):
            self.refresh_object_list(preserve_selection=True)
        
        # Auto-save after updating object
        self.save_config()
    
    def save_object(self):
        """Save current object changes (kept for backward compatibility, now calls save_all)"""
        self.save_all()
    
    def save_config(self, show_message=False):
        """Save config to file with proper formatting
        
        Args:
            show_message: If True, show success message. Default False for auto-save.
        """
        try:
            # Clean up the config structure before saving
            # Ensure all objects have proper structure
            for obj in self.config.get("game_objects", []):
                # Ensure sprites is a list
                if "sprites" not in obj:
                    obj["sprites"] = []
                # Convert sprites to proper format if needed
                if obj["sprites"]:
                    cleaned_sprites = []
                    for sprite in obj["sprites"]:
                        if isinstance(sprite, dict):
                            cleaned_sprites.append(sprite)
                        elif hasattr(sprite, 'x') and hasattr(sprite, 'y'):
                            cleaned_sprites.append({"x": sprite.x, "y": sprite.y})
                    obj["sprites"] = cleaned_sprites
                
                # Preserve all existing fields - don't remove sprite_sheet, properties, etc.
                # Only clean up legacy sprite_x/sprite_y if sprites array exists
                if obj.get("sprites") and len(obj.get("sprites", [])) > 0:
                    # Remove legacy fields only if we have sprites array
                    obj.pop("sprite_x", None)
                    obj.pop("sprite_y", None)
            
            # Write with proper formatting
            with open(self.config_path, 'w') as f:
                toml.dump(self.config, f)
            
            # Verify the saved file is valid
            try:
                with open(self.config_path, 'r') as f:
                    toml.load(f)  # Validate it can be parsed
            except Exception as e:
                self.log_status(f"Config saved but validation failed: {e}", "warning")
                return
            
            if show_message:
                self.log_status(f"Config saved to {self.config_path.name}", "success")
            # Update server status after saving
            self.root.after(500, self.check_server_status)
        except Exception as e:
            self.log_status(f"Failed to save config: {e}", "error")
    
    def find_server_process(self):
        """Find the running server process"""
        try:
            # Try to find process using port 3000
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(
                    ["lsof", "-ti", ":3000"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    pid = int(result.stdout.strip().split('\n')[0])
                    return pid
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["lsof", "-ti", ":3000"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    pid = int(result.stdout.strip().split('\n')[0])
                    return pid
            elif platform.system() == "Windows":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                for line in result.stdout.split('\n'):
                    if ':3000' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) > 0:
                            try:
                                pid = int(parts[-1])
                                return pid
                            except ValueError:
                                pass
            
            # Fallback: try to find cargo/rust process
            result = subprocess.run(
                ["ps", "aux"] if platform.system() != "Windows" else ["tasklist"],
                capture_output=True,
                text=True,
                timeout=2
            )
            for line in result.stdout.split('\n'):
                if 'tosprite' in line.lower() or ('cargo' in line.lower() and 'run' in line.lower()):
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1] if platform.system() != "Windows" else parts[1].split('.')[0])
                            return pid
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            print(f"Error finding server process: {e}")
        return None
    
    def kill_server_process(self, pid):
        """Kill the server process"""
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], timeout=5)
            else:
                os.kill(pid, signal.SIGTERM)
                # Wait a bit, then force kill if still running
                import time
                time.sleep(1)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Already dead
            return True
        except Exception as e:
            print(f"Error killing server process: {e}")
            return False
    
    def start_server(self, rebuild=False):
        """Start the server process
        
        Args:
            rebuild: If True, rebuild the project before starting
        """
        try:
            # Change to project root directory
            server_dir = self.project_root
            
            if rebuild:
                # Rebuild the project first
                self.server_status_label.config(text="Server: Rebuilding...", foreground="orange")
                self.root.update()
                
                build_process = subprocess.Popen(
                    ["cargo", "build"],
                    cwd=str(server_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = build_process.communicate()
                
                if build_process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Build failed"
                    self.log_status(f"Build failed: {error_msg[:100]}", "error")
                    return False
            
            # Always use cargo run to ensure we get the latest code
            # cargo run will rebuild automatically if needed
            self.server_process = subprocess.Popen(
                ["cargo", "run"],
                cwd=str(server_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            return True
        except Exception as e:
            print(f"Error starting server: {e}")
            return False
    
    def check_server_status(self):
        """Check if server is running and update status label"""
        pid = self.find_server_process()
        if pid:
            self.server_status_label.config(text="Server: Running", foreground="green")
        else:
            self.server_status_label.config(text="Server: Stopped", foreground="red")
    
    def shutdown_server(self):
        """Shutdown the server process"""
        pid = self.find_server_process()
        if pid:
            if messagebox.askyesno("Shutdown Server", "Are you sure you want to shutdown the server?"):
                self.server_status_label.config(text="Server: Shutting down...", foreground="orange")
                self.root.update()
                if self.kill_server_process(pid):
                    self.log_status("Server shutdown successfully", "success")
                    self.server_status_label.config(text="Server: Stopped", foreground="red")
                else:
                    self.log_status("Failed to shutdown server", "error")
                    self.server_status_label.config(text="Server: Error", foreground="red")
                self.check_server_status()
            else:
                self.log_status("Server shutdown cancelled", "info")
        else:
            self.log_status("Server is not running", "warning")
            self.server_status_label.config(text="Server: Stopped", foreground="red")
    
    def restart_server(self):
        """Restart the server"""
        try:
            # Find and kill existing server
            pid = self.find_server_process()
            if pid:
                if not messagebox.askyesno("Restart Server", 
                                          f"Server is currently running (PID: {pid}).\n\n"
                                          "Do you want to restart it?"):
                    return
                
                self.server_status_label.config(text="Server: Stopping...", foreground="orange")
                self.root.update()
                
                if not self.kill_server_process(pid):
                    self.log_status("Failed to stop the server", "error")
                    self.check_server_status()
                    return
                
                # Wait a moment for process to die and port to be released
                import time
                time.sleep(2)
                
                # Verify port is free
                check_pid = self.find_server_process()
                if check_pid:
                    # Force kill if still running
                    self.kill_server_process(check_pid)
                    time.sleep(1)
            
            # Start new server (with rebuild to ensure latest code)
            self.server_status_label.config(text="Server: Starting...", foreground="orange")
            self.root.update()
            
            if self.start_server(rebuild=True):
                # Wait a moment and check if it started
                import time
                time.sleep(3)  # Give it more time to start
                self.check_server_status()
                
                # Check if server actually started
                final_check = self.find_server_process()
                if final_check:
                    self.log_status("Server restarted successfully", "success")
                else:
                    self.server_status_label.config(text="Server: Failed", foreground="red")
                    self.log_status("Server process started but may have crashed. Check terminal for errors.", "error")
            else:
                self.server_status_label.config(text="Server: Error", foreground="red")
                self.log_status("Failed to start the server. Check terminal for errors.", "error")
        except Exception as e:
            self.log_status(f"Failed to restart server: {e}", "error")
            self.check_server_status()
    
    # Map Editor Methods
    def refresh_tile_palette(self):
        """Populate the tile palette with tiles from the config"""
        if not hasattr(self, 'tile_palette_listbox'):
            return
        if not self.config or "game_objects" not in self.config:
            return
        
        self.tile_palette_listbox.delete(0, tk.END)
        tiles = [obj for obj in self.config.get("game_objects", []) 
                 if obj.get("object_type") == "tile"]
        
        for tile in tiles:
            display_name = f"{tile.get('name', tile.get('id', 'Unknown'))} ({tile.get('id', 'unknown')})"
            self.tile_palette_listbox.insert(tk.END, display_name)
    
    def on_tile_palette_select(self, event=None):
        """Handle tile selection from palette"""
        selection = self.tile_palette_listbox.curselection()
        if selection:
            index = selection[0]
            tiles = [obj for obj in self.config.get("game_objects", []) 
                     if obj.get("object_type") == "tile"]
            if index < len(tiles):
                self.selected_tile_id = tiles[index].get("id")
                self.log_status(f"Selected tile: {tiles[index].get('name', self.selected_tile_id)}", "info")
    
    def generate_procedural_map(self):
        """Generate a procedural map using the Rust server's dungeon generator"""
        try:
            self.log_status("Generating map from Rust server...", "info")
            
            # Make HTTP request to the server's map generation endpoint
            import urllib.request
            import json
            
            url = "http://localhost:3000/api/map"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
            except urllib.error.URLError as e:
                self.log_status(f"Failed to connect to server: {e}. Make sure the server is running.", "error")
                return
            
            # Parse the response
            self.map_width = data.get("width", 80)
            self.map_height = data.get("height", 50)
            self.map_width_var.set(str(self.map_width))
            self.map_height_var.set(str(self.map_height))
            
            # Convert map tiles to tile IDs
            map_tiles = data.get("map", [])
            self.map_data = []
            for row in map_tiles:
                tile_row = []
                for tile in row:
                    # Find the tile ID that matches this tile's properties
                    # We need to match by walkable and sprite coordinates
                    tile_id = self._find_tile_id_by_properties(tile)
                    tile_row.append(tile_id)
                self.map_data.append(tile_row)
            
            # Parse entities (monsters + player)
            entities_data = data.get("entities", [])
            self.map_entities = []
            for entity in entities_data:
                self.map_entities.append({
                    "x": entity.get("x", 0),
                    "y": entity.get("y", 0),
                    "object_id": entity.get("object_id", ""),
                    "sprite_x": entity.get("sprite_x", 0),
                    "sprite_y": entity.get("sprite_y", 0),
                    "sprite_sheet": entity.get("sprite_sheet"),
                    "controller": entity.get("controller", "AI"),  # "Player" or "AI"
                })
            
            # Store stairs position
            self.map_stairs_position = data.get("stairs_position")
            
            self.render_map()
            num_monsters = sum(1 for e in self.map_entities if e.get("controller") == "AI")
            num_players = sum(1 for e in self.map_entities if e.get("controller") == "Player")
            self.log_status(f"Generated map: {self.map_width}x{self.map_height} with {num_monsters} monsters and {num_players} player(s)", "success")
        except Exception as e:
            self.log_status(f"Failed to generate map: {e}", "error")
    
    def _find_tile_id_by_properties(self, tile_data):
        """Find a tile ID that matches the given tile properties"""
        # Try to match by sprite coordinates first
        sprite_x = tile_data.get("sprite_x", 0)
        sprite_y = tile_data.get("sprite_y", 0)
        walkable = tile_data.get("walkable", False)
        
        # Look for matching tile in config
        for obj in self.config.get("game_objects", []):
            if obj.get("object_type") != "tile":
                continue
            if obj.get("walkable") != walkable:
                continue
            
            # Check if sprite matches
            sprites = obj.get("sprites", [])
            if sprites:
                for sprite in sprites:
                    if sprite.get("x") == sprite_x and sprite.get("y") == sprite_y:
                        return obj.get("id")
            # Fallback to legacy sprite_x/sprite_y
            if obj.get("sprite_x") == sprite_x and obj.get("sprite_y") == sprite_y:
                return obj.get("id")
        
        # If no exact match, return first tile with matching walkable property
        for obj in self.config.get("game_objects", []):
            if obj.get("object_type") == "tile" and obj.get("walkable") == walkable:
                return obj.get("id")
        
        # Ultimate fallback
        return "wall_dirt_top"
    
    def render_map(self):
        """Render the map on the canvas"""
        if not self.map_data:
            return
        
        self.map_canvas.delete("all")
        
        # Clear previous sprite image references to prevent memory leaks
        if hasattr(self, '_map_sprite_images'):
            self._map_sprite_images.clear()
        else:
            self._map_sprite_images = []
        
        # Load sprite sheets if needed
        sprite_sheets = {}
        
        # Render each tile
        for y in range(self.map_height):
            for x in range(self.map_width):
                tile_id = self.map_data[y][x]
                
                # Find the tile object
                tile_obj = None
                for obj in self.config.get("game_objects", []):
                    if obj.get("id") == tile_id and obj.get("object_type") == "tile":
                        tile_obj = obj
                        break
                
                if not tile_obj:
                    # Draw a placeholder rectangle (scaled by zoom)
                    scaled_size = int(self.tile_size * self.map_zoom_level)
                    self.map_canvas.create_rectangle(
                        x * scaled_size, y * scaled_size,
                        (x + 1) * scaled_size, (y + 1) * scaled_size,
                        fill="gray", outline="black"
                    )
                    continue
                
                # Get sprite coordinates
                sprites = tile_obj.get("sprites", [])
                if not sprites:
                    # Fallback to legacy sprite_x/sprite_y
                    sprite_x = tile_obj.get("sprite_x", 0)
                    sprite_y = tile_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                # Use first sprite (or randomize later)
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                
                # Get sprite sheet
                sprite_sheet = tile_obj.get("sprite_sheet", "tiles.png")
                
                # Load sprite sheet if not already loaded
                if sprite_sheet not in sprite_sheets:
                    sheet_path = self.assets_dir / sprite_sheet
                    if sheet_path.exists():
                        try:
                            img = Image.open(sheet_path)
                            sprite_sheets[sprite_sheet] = img
                        except Exception as e:
                            self.log_status(f"Failed to load sprite sheet {sprite_sheet}: {e}", "error")
                            sprite_sheets[sprite_sheet] = None
                    else:
                        sprite_sheets[sprite_sheet] = None
                
                # Draw the tile
                if sprite_sheets.get(sprite_sheet):
                    img = sprite_sheets[sprite_sheet]
                    # Extract sprite from sprite sheet
                    left = sprite_x * self.tile_size
                    top = sprite_y * self.tile_size
                    right = left + self.tile_size
                    bottom = top + self.tile_size
                    
                    try:
                        sprite_img = img.crop((left, top, right, bottom))
                        scaled_size = int(self.tile_size * self.map_zoom_level)
                        sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        # Store reference to prevent garbage collection
                        if not hasattr(self, '_map_sprite_images'):
                            self._map_sprite_images = []
                        self._map_sprite_images.append(sprite_photo)
                        
                        self.map_canvas.create_image(
                            x * scaled_size, y * scaled_size,
                            anchor=tk.NW, image=sprite_photo
                        )
                    except Exception as e:
                        # Fallback: draw colored rectangle (scaled by zoom)
                        color = "lightgray" if tile_obj.get("walkable", False) else "darkgray"
                        scaled_size = int(self.tile_size * self.map_zoom_level)
                        self.map_canvas.create_rectangle(
                            x * scaled_size, y * scaled_size,
                            (x + 1) * scaled_size, (y + 1) * scaled_size,
                            fill=color, outline="black"
                        )
                else:
                    # Fallback: draw colored rectangle (scaled by zoom)
                    color = "lightgray" if tile_obj.get("walkable", False) else "darkgray"
                    scaled_size = int(self.tile_size * self.map_zoom_level)
                    self.map_canvas.create_rectangle(
                        x * scaled_size, y * scaled_size,
                        (x + 1) * scaled_size, (y + 1) * scaled_size,
                        fill=color, outline="black"
                    )
        
        # Render entities (monsters + player) on top of tiles
        for entity in self.map_entities:
            entity_x = entity.get("x", 0)
            entity_y = entity.get("y", 0)
            object_id = entity.get("object_id", "")
            sprite_x = entity.get("sprite_x", 0)
            sprite_y = entity.get("sprite_y", 0)
            sprite_sheet = entity.get("sprite_sheet")
            controller = entity.get("controller", "AI")  # "Player" or "AI"
            
            # Find the entity object
            entity_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("id") == object_id:
                    entity_obj = obj
                    break
            
            if entity_obj:
                # Use sprite from entity data or from object
                if sprite_sheet:
                    sheet_path = self.assets_dir / sprite_sheet
                    if sheet_path.exists():
                        try:
                            img = Image.open(sheet_path)
                            # Extract sprite from sprite sheet
                            left = sprite_x * self.tile_size
                            top = sprite_y * self.tile_size
                            right = left + self.tile_size
                            bottom = top + self.tile_size
                            
                            sprite_img = img.crop((left, top, right, bottom))
                            scaled_size = int(self.tile_size * self.map_zoom_level)
                            sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                            sprite_photo = ImageTk.PhotoImage(sprite_img)
                            
                            # Store reference
                            self._map_sprite_images.append(sprite_photo)
                            
                            # Draw entity on top of tile (scaled by zoom)
                            self.map_canvas.create_image(
                                entity_x * scaled_size, entity_y * scaled_size,
                                anchor=tk.NW, image=sprite_photo
                            )
                            # Add colored border to distinguish player (green) from monsters (red)
                            if controller == "Player":
                                self.map_canvas.create_rectangle(
                                    entity_x * scaled_size, entity_y * scaled_size,
                                    (entity_x + 1) * scaled_size, (entity_y + 1) * scaled_size,
                                    outline="lime", width=max(2, int(3 * self.map_zoom_level))
                                )
                        except Exception as e:
                            # Fallback: draw a colored circle for entity (scaled by zoom)
                            scaled_size = int(self.tile_size * self.map_zoom_level)
                            offset = max(1, int(4 * self.map_zoom_level))
                            # Use green for player, red for monsters
                            color = "green" if controller == "Player" else "red"
                            outline_color = "darkgreen" if controller == "Player" else "darkred"
                            self.map_canvas.create_oval(
                                entity_x * scaled_size + offset, entity_y * scaled_size + offset,
                                (entity_x + 1) * scaled_size - offset, (entity_y + 1) * scaled_size - offset,
                                fill=color, outline=outline_color, width=max(1, int(2 * self.map_zoom_level))
                            )
                    else:
                        # Fallback: draw a colored circle for entity (scaled by zoom)
                        scaled_size = int(self.tile_size * self.map_zoom_level)
                        offset = max(1, int(4 * self.map_zoom_level))
                        # Use green for player, red for monsters
                        color = "green" if controller == "Player" else "red"
                        outline_color = "darkgreen" if controller == "Player" else "darkred"
                        self.map_canvas.create_oval(
                            entity_x * scaled_size + offset, entity_y * scaled_size + offset,
                            (entity_x + 1) * scaled_size - offset, (entity_y + 1) * scaled_size - offset,
                            fill=color, outline=outline_color, width=max(1, int(2 * self.map_zoom_level))
                        )
                else:
                    # Fallback: draw a colored circle for entity (scaled by zoom)
                    scaled_size = int(self.tile_size * self.map_zoom_level)
                    offset = max(1, int(4 * self.map_zoom_level))
                    # Use green for player, red for monsters
                    color = "green" if controller == "Player" else "red"
                    outline_color = "darkgreen" if controller == "Player" else "darkred"
                    self.map_canvas.create_oval(
                        entity_x * scaled_size + offset, entity_y * scaled_size + offset,
                        (entity_x + 1) * scaled_size - offset, (entity_y + 1) * scaled_size - offset,
                        fill=color, outline=outline_color, width=max(1, int(2 * self.map_zoom_level))
                    )
        
        # Render stairs (goal object) on top of everything
        if self.map_stairs_position and isinstance(self.map_stairs_position, list) and len(self.map_stairs_position) == 2:
            stairs_x = self.map_stairs_position[0]
            stairs_y = self.map_stairs_position[1]
            scaled_size = int(self.tile_size * self.map_zoom_level)
            dest_x = stairs_x * scaled_size
            dest_y = stairs_y * scaled_size
            
            # Find stairs object to get sprite info
            stairs_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("id") == "stairs":
                    stairs_obj = obj
                    break
            
            if stairs_obj:
                sprite_sheet = stairs_obj.get("sprite_sheet", "tiles.png")
                sprites = stairs_obj.get("sprites", [])
                if sprites:
                    sprite = sprites[0]
                    sprite_x = sprite.get("x", 7)
                    sprite_y = sprite.get("y", 16)
                else:
                    sprite_x = 7
                    sprite_y = 16
                
                # Load and render stairs sprite
                sheet_path = self.assets_dir / sprite_sheet
                if sheet_path.exists():
                    try:
                        img = Image.open(sheet_path)
                        left = sprite_x * self.tile_size
                        top = sprite_y * self.tile_size
                        right = left + self.tile_size
                        bottom = top + self.tile_size
                        
                        sprite_img = img.crop((left, top, right, bottom))
                        sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        # Store reference
                        if not hasattr(self, '_map_sprite_images'):
                            self._map_sprite_images = []
                        self._map_sprite_images.append(sprite_photo)
                        
                        # Draw stairs
                        self.map_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                        
                        # Add bright cyan border to make stairs visible
                        self.map_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + scaled_size, dest_y + scaled_size,
                            outline="cyan", width=max(2, int(3 * self.map_zoom_level))
                        )
                    except Exception as e:
                        # Fallback: draw bright yellow rectangle with cyan border
                        self.map_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + scaled_size, dest_y + scaled_size,
                            fill="yellow", outline="cyan", width=max(2, int(3 * self.map_zoom_level))
                        )
                else:
                    # Fallback: draw bright yellow rectangle with cyan border
                    self.map_canvas.create_rectangle(
                        dest_x, dest_y,
                        dest_x + scaled_size, dest_y + scaled_size,
                        fill="yellow", outline="cyan", width=max(2, int(3 * self.map_zoom_level))
                    )
            else:
                # Fallback: draw bright yellow rectangle with cyan border
                self.map_canvas.create_rectangle(
                    dest_x, dest_y,
                    dest_x + scaled_size, dest_y + scaled_size,
                    fill="yellow", outline="cyan", width=max(2, int(3 * self.map_zoom_level))
                )
        
        # Update scroll region
        self.map_canvas.config(scrollregion=self.map_canvas.bbox("all"))

def main():
    root = tk.Tk()
    app = GameObjectEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()

