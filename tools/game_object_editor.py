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
import urllib.request
import urllib.error

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
        self.schema = None  # Dynamic schema loaded from server
        
        # Fullscreen map preview
        self.level_map_fullscreen_window = None
        self.level_map_fullscreen_canvas = None
        self.level_map_fullscreen_zoom_level = 1.0
        
        # Load schema first (needed for UI creation)
        self.load_schema()
        
        # Create UI
        self.create_ui()
        
        # Load data
        self.load_config()
        
        # Validate config after loading - check for missing required parameters
        self.validate_config()
        
        self.refresh_sprite_sheets()  # Populate sprite sheet list
        self.load_sprite_sheet()  # Load default sprite sheet
        
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
        
        # Create Level Editor tab
        self.level_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.level_tab, text="Level Editor")
        
        # Build Game Objects tab UI
        self.create_objects_tab_ui()
        
        # Build Level Editor tab UI
        self.create_level_tab_ui()
        
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
        
        # Build property schema dynamically from loaded schema
        # Filter out hidden fields (label=None) and build schema dict
        self.property_schema = {}
        if self.schema and "fields" in self.schema:
            for field in self.schema["fields"]:
                if field.get("label") is None:  # Skip hidden fields
                    continue
                
                field_name = field["name"]
                field_type = field["field_type"]
                show_for_types = field.get("show_for_types", [])
                label = field.get("label", field_name.capitalize())
                
                # Map Rust types to Python types
                if field_type == "bool" or field_type == "Option<bool>":
                    dtype = bool
                elif "i32" in field_type or "u32" in field_type:
                    dtype = int
                else:
                    dtype = str
                
                # Determine if always show (empty show_for_types means show for all)
                always_show = len(show_for_types) == 0
                
                self.property_schema[field_name] = (f"{label}:", field_name, dtype, always_show, show_for_types)
        else:
            # Fallback to empty schema if schema not loaded
            self.property_schema = {}
        
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
                                  values=["tile", "character", "goal", "consumable", "chest"], width=17)
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
        
        # Interactable section (for chests, doors, etc.)
        # For interactable objects: sprites[0] = before (closed), sprites[1] = after (open)
        # Before is always non-walkable, after is always walkable
        self.interactable_row = sprite_row + 3
        self.interactable_frame = ttk.LabelFrame(middle_panel, text="Interactable (Before/After States)", padding="5")
        self.interactable_frame.grid(row=self.interactable_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(20, 5))
        
        ttk.Label(self.interactable_frame, text="For interactable objects:", font=("Arial", 9)).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        ttk.Label(self.interactable_frame, text="• sprites[0] = Before state (closed, non-walkable)", font=("Arial", 8)).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.interactable_frame, text="• sprites[1] = After state (open, walkable)", font=("Arial", 8)).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Info label
        info_label = ttk.Label(self.interactable_frame, 
                              text="Use the main 'Sprites' list above. First sprite = closed, second sprite = open.",
                              font=("Arial", 8), foreground="gray", wraplength=300)
        info_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        # Custom properties removed - all properties are now defined in schema
        
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
    
    def _load_interactable_data(self, obj):
        """Show/hide interactable frame based on object type"""
        obj_type = obj.get("object_type", "")
        if obj_type == "chest":
            self.interactable_frame.grid()
        else:
            self.interactable_frame.grid_remove()
    
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
        
        # Show/hide interactable frame based on object type
        if obj_type == "chest":
            self.interactable_frame.grid()
        else:
            self.interactable_frame.grid_remove()
    
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
            self.config = {"game_objects": [], "levels": []}
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
            
            # Ensure levels array exists
            if "levels" not in self.config:
                self.config["levels"] = []
            
            self.refresh_object_list()
            # Refresh tile palette if UI is already created
            if hasattr(self, 'tile_palette_listbox'):
                self.refresh_tile_palette()
            # Refresh level list if UI is already created
            if hasattr(self, 'level_listbox'):
                self.refresh_level_list()
                self.refresh_monster_list()
            self.log_status(f"Loaded {len(self.config.get('game_objects', []))} game objects", "success")
        except Exception as e:
            self.log_status(f"Failed to load config: {e}", "error")
            self.config = {"game_objects": []}
    
    def load_schema(self):
        """Load GameObject schema from server endpoint or use defaults"""
        schema_path = self.project_root / "game_object_schema.json"
        
        # Try to load from local file first
        if schema_path.exists():
            try:
                with open(schema_path, 'r') as f:
                    self.schema = json.load(f)
                if not hasattr(self, 'status_label') or not self.status_label:
                    print("Loaded schema from local file")
                else:
                    self.log_status("Loaded schema from local file", "success")
                return
            except Exception as e:
                if hasattr(self, 'status_label') and self.status_label:
                    self.log_status(f"Failed to load schema from file: {e}", "warning")
        
        # Try to fetch from server
        try:
            url = "http://localhost:3000/api/schema"
            with urllib.request.urlopen(url, timeout=2) as response:
                self.schema = json.loads(response.read().decode())
                # Save to local file for offline use
                with open(schema_path, 'w') as f:
                    json.dump(self.schema, f, indent=2)
                if hasattr(self, 'status_label') and self.status_label:
                    self.log_status("Loaded schema from server", "success")
                return
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            # Server not running or endpoint not available - use hardcoded fallback
            if hasattr(self, 'status_label') and self.status_label:
                self.log_status("Server not available, using default schema", "warning")
            self.schema = self._get_default_schema()
    
    def _get_default_schema(self):
        """Fallback schema if server is not available"""
        return {
            "fields": [
                {"name": "id", "field_type": "String", "optional": False, "default": None, "show_for_types": [], "label": "ID"},
                {"name": "name", "field_type": "String", "optional": False, "default": None, "show_for_types": [], "label": "Name"},
                {"name": "object_type", "field_type": "String", "optional": False, "default": None, "show_for_types": [], "label": "Type"},
                {"name": "walkable", "field_type": "bool", "optional": False, "default": "false", "show_for_types": ["tile"], "label": "Walkable"},
                {"name": "health", "field_type": "Option<u32>", "optional": True, "default": None, "show_for_types": ["character", "item"], "label": "Health"},
                {"name": "attack", "field_type": "Option<i32>", "optional": True, "default": None, "show_for_types": ["character", "item"], "label": "Attack"},
                {"name": "defense", "field_type": "Option<i32>", "optional": True, "default": None, "show_for_types": ["character", "item"], "label": "Defense"},
                {"name": "attack_spread_percent", "field_type": "Option<u32>", "optional": True, "default": "20", "show_for_types": ["character", "item"], "label": "Attack Spread %"},
                {"name": "crit_chance_percent", "field_type": "Option<u32>", "optional": True, "default": "0", "show_for_types": ["character", "item"], "label": "Crit Chance %"},
                {"name": "crit_damage_percent", "field_type": "Option<u32>", "optional": True, "default": "150", "show_for_types": ["character", "item"], "label": "Crit Damage %"},
                {"name": "monster", "field_type": "Option<bool>", "optional": True, "default": "false", "show_for_types": ["character"], "label": "Monster"},
                {"name": "healing_power", "field_type": "Option<u32>", "optional": True, "default": None, "show_for_types": ["consumable"], "label": "Healing Power"},
                {"name": "sprites", "field_type": "Vec<SpriteCoord>", "optional": False, "default": "[]", "show_for_types": [], "label": "Sprites"},
                {"name": "interactable", "field_type": "Option<InteractableData>", "optional": True, "default": None, "show_for_types": ["chest"], "label": "Interactable"},
                {"name": "sprite_sheet", "field_type": "Option<String>", "optional": True, "default": None, "show_for_types": [], "label": "Sprite Sheet"},
            ]
        }
    
    def get_required_schema(self):
        """Define the required schema for GameObject based on current Rust struct
        
        Returns:
            dict: {
                'required_fields': [list of always-required fields],
                'type_specific': {
                    'character': [list of required fields for characters],
                    'consumable': [list of required fields for consumables],
                    ...
                }
            }
        """
        return {
            'required_fields': [
                'id',           # Always required
                'name',         # Always required
                'object_type',  # Always required
                'walkable',     # Always required
                'sprites',      # Always required (array, can be empty but must exist)
            ],
            'type_specific': {
                'character': [
                    # Characters should have attack (default 0 if not set)
                    # Characters should have monster flag (default false)
                ],
                'consumable': [
                    'healing_power',  # Consumables must have healing_power
                ],
            },
            'optional_fields': [
                'health',        # Optional for all types
                'attack',        # Optional (defaults handled in code)
                'monster',       # Optional (defaults to false)
                'healing_power', # Required for consumables, optional otherwise
                'sprite_sheet',  # Optional but recommended
                'sprite_x',      # Legacy, optional
                'sprite_y',      # Legacy, optional
                'properties',    # Optional (defaults to empty dict)
            ]
        }
    
    def validate_config(self):
        """Validate all game objects against the required schema
        
        Shows a dialog forcing user to fix missing required parameters before continuing.
        """
        if not self.config or "game_objects" not in self.config:
            return
        
        schema = self.get_required_schema()
        required_fields = schema['required_fields']
        type_specific = schema['type_specific']
        
        issues = []  # List of (object_index, object_id, object_name, missing_fields)
        
        for idx, obj in enumerate(self.config.get("game_objects", [])):
            missing_fields = []
            obj_type = obj.get("object_type", "unknown")
            
            # Check required fields (always required)
            for field in required_fields:
                if field == 'sprites':
                    # sprites must exist as a list (can be empty)
                    if 'sprites' not in obj or not isinstance(obj.get('sprites'), list):
                        missing_fields.append('sprites')
                elif field not in obj:
                    missing_fields.append(field)
            
            # Check type-specific required fields
            if obj_type in type_specific:
                for field in type_specific[obj_type]:
                    if field not in obj or obj[field] is None:
                        missing_fields.append(field)
            
            if missing_fields:
                issues.append((idx, obj.get('id', f'object_{idx}'), obj.get('name', 'Unnamed'), missing_fields))
        
        if issues:
            # Show validation dialog
            self.show_validation_dialog(issues)
    
    def show_validation_dialog(self, issues):
        """Show a dialog listing all objects with missing required parameters
        
        Args:
            issues: List of (object_index, object_id, object_name, missing_fields)
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Config Validation Required")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()  # Make it modal
        
        # Message
        msg_frame = ttk.Frame(dialog, padding="10")
        msg_frame.pack(fill=tk.X)
        
        ttk.Label(
            msg_frame,
            text="Some game objects are missing required parameters.",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        
        ttk.Label(
            msg_frame,
            text="Please update all objects below before continuing.",
            foreground="red"
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # List of issues
        list_frame = ttk.Frame(dialog, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable list
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Courier", 9))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate list
        for idx, obj_id, obj_name, missing_fields in issues:
            obj_display = f"[{obj_id}] {obj_name}"
            missing_str = ", ".join(missing_fields)
            listbox.insert(tk.END, f"{obj_display}")
            listbox.insert(tk.END, f"  Missing: {missing_str}")
            listbox.insert(tk.END, "")  # Empty line
        
        # Buttons
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        
        def go_to_object(event=None):
            selection = listbox.curselection()
            if selection:
                # Find which object this corresponds to
                line_idx = selection[0]
                # Each object takes 3 lines (name, missing, empty)
                obj_idx = line_idx // 3
                if obj_idx < len(issues):
                    actual_obj_idx = issues[obj_idx][0]
                    # Select the object in the main list
                    self.object_listbox.selection_clear(0, tk.END)
                    self.object_listbox.selection_set(actual_obj_idx)
                    self.object_listbox.see(actual_obj_idx)
                    self.on_object_select(None)
                    dialog.destroy()
        
        def fix_all():
            """Try to fix all issues with default values"""
            fixed_count = 0
            for idx, obj_id, obj_name, missing_fields in issues:
                obj = self.config["game_objects"][idx]
                obj_type = obj.get("object_type", "unknown")
                
                for field in missing_fields:
                    if field == 'sprites':
                        obj['sprites'] = []
                        # Try to create from legacy sprite_x/sprite_y if available
                        if 'sprite_x' in obj and 'sprite_y' in obj:
                            obj['sprites'] = [{"x": obj['sprite_x'], "y": obj['sprite_y']}]
                        fixed_count += 1
                    elif field == 'healing_power' and obj_type == 'consumable':
                        obj['healing_power'] = 20  # Default healing power
                        fixed_count += 1
                    # Add more default values as needed
            
            if fixed_count > 0:
                self.log_status(f"Auto-fixed {fixed_count} missing fields with defaults", "success")
                self.save_config()
                dialog.destroy()
                # Re-validate to check if there are still issues
                self.validate_config()
            else:
                messagebox.showinfo("Cannot Auto-Fix", "Some fields require manual input. Please fix them manually.")
        
        ttk.Button(button_frame, text="Go to Selected Object", command=go_to_object).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Try Auto-Fix Missing Fields", command=fix_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close (I'll fix manually)", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Double-click to go to object
        listbox.bind('<Double-Button-1>', go_to_object)
        
        # Focus on listbox
        listbox.focus_set()
    
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
    def _find_tile_id_by_properties(self, tile_data):
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
        
        # Load interactable data
        self._load_interactable_data(obj)
        
        # Custom properties removed - all properties are now in schema
        
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
                # Clear form
                for var, _ in self.prop_vars.values():
                    if isinstance(var, tk.BooleanVar):
                        var.set(False)
                    else:
                        var.set("")
                # Custom properties removed
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
        
        # For all objects (including chests), use regular sprite array
        # For chests: sprites[0] = closed, sprites[1] = open
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
                val = var.get().strip()
                self.current_object["health"] = int(val) if val and val.lower() != "none" else None
            elif key == "attack":
                val = var.get().strip()
                # Store attack as top-level property (not in properties map)
                self.current_object["attack"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "attack" in self.current_object["properties"]:
                    del self.current_object["properties"]["attack"]
            elif key == "defense":
                val = var.get().strip()
                # Store defense as top-level property (not in properties map)
                self.current_object["defense"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "defense" in self.current_object["properties"]:
                    del self.current_object["properties"]["defense"]
            elif key == "attack_spread_percent":
                val = var.get().strip()
                # Store attack_spread_percent as top-level property (not in properties map)
                self.current_object["attack_spread_percent"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "attack_spread_percent" in self.current_object["properties"]:
                    del self.current_object["properties"]["attack_spread_percent"]
            elif key == "crit_chance_percent":
                val = var.get().strip()
                # Store crit_chance_percent as top-level property (not in properties map)
                self.current_object["crit_chance_percent"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "crit_chance_percent" in self.current_object["properties"]:
                    del self.current_object["properties"]["crit_chance_percent"]
            elif key == "crit_damage_percent":
                val = var.get().strip()
                # Store crit_damage_percent as top-level property (not in properties map)
                self.current_object["crit_damage_percent"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "crit_damage_percent" in self.current_object["properties"]:
                    del self.current_object["properties"]["crit_damage_percent"]
            elif key == "healing_power":
                val = var.get().strip()
                # Store healing_power as top-level property (not in properties map)
                self.current_object["healing_power"] = int(val) if val and val.lower() != "none" else None
                # Remove from properties map if it was there
                if "properties" in self.current_object and "healing_power" in self.current_object["properties"]:
                    del self.current_object["properties"]["healing_power"]
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
                val = var.get().strip() if isinstance(var.get(), str) else str(var.get())
                # Handle "None" string and empty values
                if not val or val.lower() == "none":
                    # Only set to None if this is an optional field (not required)
                    # For required int fields, use 0 as default
                    self.current_object[key] = None if key in ["health", "attack", "defense", "attack_spread_percent", "crit_chance_percent", "crit_damage_percent", "healing_power"] else 0
                else:
                    try:
                        self.current_object[key] = int(val)
                    except ValueError:
                        self.current_object[key] = 0
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
        
        # Update interactable data - for chest objects, set interactable marker if sprites array has at least 2 sprites
        obj_type = self.current_object.get("object_type", "")
        if obj_type == "chest":
            # If we have at least 2 sprites, mark as interactable
            if len(sprites) >= 2:
                self.current_object["interactable"] = {}  # Empty object - just a marker
            else:
                # Remove interactable if not enough sprites
                self.current_object.pop("interactable", None)
        else:
            # Remove interactable if not a chest
            self.current_object.pop("interactable", None)
        
        # Preserve sprite_sheet if it exists - don't remove it
        # It will be updated by the form field if changed, but won't be removed
        
        # Custom properties removed - all properties are now handled through schema fields
        # Ensure properties map exists for backward compatibility but keep it empty
        if "properties" not in self.current_object:
            self.current_object["properties"] = {}
        
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
        # Validate before saving
        schema = self.get_required_schema()
        required_fields = schema['required_fields']
        type_specific = schema['type_specific']
        
        issues = []
        for idx, obj in enumerate(self.config.get("game_objects", [])):
            missing_fields = []
            obj_type = obj.get("object_type", "unknown")
            
            # Check required fields
            for field in required_fields:
                if field == 'sprites':
                    if 'sprites' not in obj or not isinstance(obj.get('sprites'), list):
                        missing_fields.append('sprites')
                elif field not in obj:
                    missing_fields.append(field)
            
            # Check type-specific
            if obj_type in type_specific:
                for field in type_specific[obj_type]:
                    if field not in obj or obj[field] is None:
                        missing_fields.append(field)
            
            if missing_fields:
                issues.append((idx, obj.get('id', f'object_{idx}'), obj.get('name', 'Unnamed'), missing_fields))
        
        if issues:
            # Show validation dialog and prevent save
            self.show_validation_dialog(issues)
            self.log_status("Cannot save: Some objects are missing required parameters", "error")
            return False
        
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
            return True
        except Exception as e:
            self.log_status(f"Failed to save config: {e}", "error")
            return False
    
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
    
    def create_level_tab_ui(self):
        """Create the UI for the Level Editor tab"""
        # Left panel - Level list
        left_panel = ttk.LabelFrame(self.level_tab, text="Levels", padding="10")
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        ttk.Label(left_panel, text="Levels", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Level listbox with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.level_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, width=25)
        self.level_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.level_listbox.bind('<<ListboxSelect>>', self.on_level_select)
        scrollbar.config(command=self.level_listbox.yview)
        
        # Level buttons
        level_btn_frame = ttk.Frame(left_panel)
        level_btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(level_btn_frame, text="Add Level", command=self.add_level).pack(fill=tk.X, pady=2)
        ttk.Button(level_btn_frame, text="Delete Level", command=self.delete_level).pack(fill=tk.X, pady=2)
        
        # Middle panel - Level properties
        middle_panel = ttk.LabelFrame(self.level_tab, text="Level Properties", padding="10")
        middle_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Level number
        ttk.Label(middle_panel, text="Level Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.level_number_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.level_number_var, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Min/Max rooms
        ttk.Label(middle_panel, text="Min Rooms:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.min_rooms_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.min_rooms_var, width=20).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(middle_panel, text="Max Rooms:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_rooms_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.max_rooms_var, width=20).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Min/Max monsters per room
        ttk.Label(middle_panel, text="Min Monsters/Room:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.min_monsters_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.min_monsters_var, width=20).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(middle_panel, text="Max Monsters/Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.max_monsters_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.max_monsters_var, width=20).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Chest count
        ttk.Label(middle_panel, text="Chest Count:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.chest_count_var = tk.StringVar()
        ttk.Entry(middle_panel, textvariable=self.chest_count_var, width=20).grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Allowed monsters
        ttk.Label(middle_panel, text="Allowed Monsters:", font=("Arial", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky=tk.W, pady=(20, 5))
        
        # Monster selection listbox
        monster_list_frame = ttk.Frame(middle_panel)
        monster_list_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        monster_scrollbar = ttk.Scrollbar(monster_list_frame)
        monster_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.allowed_monsters_listbox = tk.Listbox(monster_list_frame, yscrollcommand=monster_scrollbar.set, 
                                                   height=8, selectmode=tk.MULTIPLE)
        self.allowed_monsters_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        monster_scrollbar.config(command=self.allowed_monsters_listbox.yview)
        
        # Populate monster list with available monsters
        self.refresh_monster_list()
        
        # Right panel - Map preview and generation
        right_panel = ttk.LabelFrame(self.level_tab, text="Map Preview", padding="10")
        right_panel.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Generate button
        ttk.Button(right_panel, text="Generate Map with Level Settings", 
                  command=self.generate_level_map, 
                  style="Accent.TButton").pack(fill=tk.X, pady=5)
        
        # Fullscreen button
        ttk.Button(right_panel, text="Fullscreen Preview (F)", 
                  command=self.fullscreen_level_map).pack(fill=tk.X, pady=5)
        
        ttk.Separator(right_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Canvas with scrollbars for map
        canvas_frame = ttk.Frame(right_panel)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Use the same map_canvas from map tab, or create a new one for level editor
        # For now, create a separate one for level editor
        self.level_map_canvas = tk.Canvas(canvas_frame, width=600, height=600, bg="black",
                                          yscrollcommand=v_scrollbar.set,
                                          xscrollcommand=h_scrollbar.set)
        self.level_map_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.level_map_canvas.yview)
        h_scrollbar.config(command=self.level_map_canvas.xview)
        
        # Map zoom controls
        zoom_frame = ttk.Frame(right_panel)
        zoom_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(zoom_frame, text="Zoom In (+)", command=self.level_map_zoom_in, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom Out (-)", command=self.level_map_zoom_out, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Reset (1x)", command=self.level_map_zoom_reset, width=12).pack(side=tk.LEFT, padx=2)
        self.level_map_zoom_label = ttk.Label(zoom_frame, text="Zoom: 100%")
        self.level_map_zoom_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Map canvas mouse wheel support for zoom
        self.level_map_canvas.bind("<MouseWheel>", self.on_level_map_mousewheel)  # Windows/Linux
        self.level_map_canvas.bind("<Button-4>", lambda e: self.level_map_zoom_in())  # macOS scroll up
        self.level_map_canvas.bind("<Button-5>", lambda e: self.level_map_zoom_out())  # macOS scroll down
        # Make canvas focusable for mouse wheel
        self.level_map_canvas.bind("<Enter>", lambda e: self.level_map_canvas.focus_set())
        self.level_map_canvas.bind("<Leave>", lambda e: self.root.focus_set())
        
        # Level map data (separate from map tab)
        self.level_map_data = None
        self.level_map_width = 80
        self.level_map_height = 50
        self.level_map_entities = []
        self.level_map_rooms = []
        self.level_map_zoom_level = 1.0
        self.level_map_stairs_position = None
        
        # Configure grid weights
        self.level_tab.columnconfigure(2, weight=1)
        self.level_tab.columnconfigure(1, weight=0)
        self.level_tab.rowconfigure(0, weight=1)
        middle_panel.columnconfigure(1, weight=1)
    
    def refresh_monster_list(self):
        """Populate the monster listbox with available monster characters"""
        if not hasattr(self, 'allowed_monsters_listbox'):
            return
        if not self.config or "game_objects" not in self.config:
            return
        
        self.allowed_monsters_listbox.delete(0, tk.END)
        
        # Get all monster characters
        monsters = []
        for obj in self.config.get("game_objects", []):
            if obj.get("object_type") == "character":
                monster = obj.get("monster", False)
                if isinstance(monster, bool) and monster:
                    monsters.append(obj)
                elif isinstance(monster, str) and monster.lower() == "true":
                    monsters.append(obj)
                elif "properties" in obj and obj["properties"].get("monster") == "true":
                    monsters.append(obj)
        
        # Sort by name
        monsters.sort(key=lambda x: x.get("name", x.get("id", "")))
        
        for monster in monsters:
            name = monster.get("name", monster.get("id", "Unknown"))
            self.allowed_monsters_listbox.insert(tk.END, name)
    
    def on_level_select(self, event):
        """Handle level selection"""
        selection = self.level_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        levels = self.config.get("levels", [])
        if index >= len(levels):
            return
        
        level = levels[index]
        self.current_level = level
        
        # Load level data into form
        self.level_number_var.set(str(level.get("level_number", 1)))
        self.min_rooms_var.set(str(level.get("min_rooms", 8)))
        self.max_rooms_var.set(str(level.get("max_rooms", 12)))
        self.min_monsters_var.set(str(level.get("min_monsters_per_room", 1)))
        self.max_monsters_var.set(str(level.get("max_monsters_per_room", 1)))
        self.chest_count_var.set(str(level.get("chest_count", 5)))
        
        # Select allowed monsters
        self.allowed_monsters_listbox.selection_clear(0, tk.END)
        allowed = level.get("allowed_monsters", [])
        
        # Get monster names for matching
        monsters = []
        for obj in self.config.get("game_objects", []):
            if obj.get("object_type") == "character":
                monster = obj.get("monster", False)
                if isinstance(monster, bool) and monster:
                    monsters.append(obj)
                elif isinstance(monster, str) and monster.lower() == "true":
                    monsters.append(obj)
                elif "properties" in obj and obj["properties"].get("monster") == "true":
                    monsters.append(obj)
        
        monsters.sort(key=lambda x: x.get("name", x.get("id", "")))
        
        for i, monster in enumerate(monsters):
            monster_id = monster.get("id", "")
            if monster_id in allowed:
                self.allowed_monsters_listbox.selection_set(i)
    
    def add_level(self):
        """Add a new level"""
        if "levels" not in self.config:
            self.config["levels"] = []
        
        # Find next level number
        existing_levels = self.config["levels"]
        next_level = 1
        if existing_levels:
            max_level = max(level.get("level_number", 1) for level in existing_levels)
            next_level = max_level + 1
        
        # Get all monster IDs as default
        monster_ids = []
        for obj in self.config.get("game_objects", []):
            if obj.get("object_type") == "character":
                monster = obj.get("monster", False)
                if isinstance(monster, bool) and monster:
                    monster_ids.append(obj.get("id", ""))
                elif isinstance(monster, str) and monster.lower() == "true":
                    monster_ids.append(obj.get("id", ""))
                elif "properties" in obj and obj["properties"].get("monster") == "true":
                    monster_ids.append(obj.get("id", ""))
        
        new_level = {
            "level_number": next_level,
            "min_rooms": 8,
            "max_rooms": 12,
            "min_monsters_per_room": 1,
            "max_monsters_per_room": 1,
            "chest_count": 5,
            "allowed_monsters": monster_ids,
        }
        
        self.config["levels"].append(new_level)
        self.save_config()
        self.refresh_level_list()
        self.log_status(f"Added level {next_level}", "success")
    
    def delete_level(self):
        """Delete selected level"""
        selection = self.level_listbox.curselection()
        if not selection:
            self.log_status("No level selected", "error")
            return
        
        index = selection[0]
        levels = self.config.get("levels", [])
        if index >= len(levels):
            return
        
        level = levels[index]
        level_num = level.get("level_number", index + 1)
        
        if messagebox.askyesno("Confirm Delete", f"Delete level {level_num}?"):
            del levels[index]
            self.save_config()
            self.refresh_level_list()
            self.log_status(f"Deleted level {level_num}", "success")
    
    def refresh_level_list(self):
        """Refresh the level listbox"""
        if not hasattr(self, 'level_listbox'):
            return
        
        self.level_listbox.delete(0, tk.END)
        
        if not self.config or "levels" not in self.config:
            return
        
        levels = self.config["levels"]
        # Sort by level number
        sorted_levels = sorted(levels, key=lambda x: x.get("level_number", 0))
        
        for level in sorted_levels:
            level_num = level.get("level_number", 0)
            self.level_listbox.insert(tk.END, f"Level {level_num}")
        
        # Auto-save level changes when fields change (set up once)
        if not hasattr(self, '_level_traces_setup'):
            for var in [self.level_number_var, self.min_rooms_var, self.max_rooms_var, 
                       self.min_monsters_var, self.max_monsters_var, self.chest_count_var]:
                var.trace_add("write", lambda *args: self._save_current_level_changes())
            self._level_traces_setup = True
    
    def _save_current_level_changes(self):
        """Save current level changes to config"""
        if not hasattr(self, 'level_listbox') or not self.level_listbox:
            return
        
        selection = self.level_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        levels = self.config.get("levels", [])
        if index >= len(levels):
            return
        
        level = levels[index]
        
        try:
            level["level_number"] = int(self.level_number_var.get())
            level["min_rooms"] = int(self.min_rooms_var.get())
            level["max_rooms"] = int(self.max_rooms_var.get())
            level["min_monsters_per_room"] = int(self.min_monsters_var.get())
            level["max_monsters_per_room"] = int(self.max_monsters_var.get())
            level["chest_count"] = int(self.chest_count_var.get())
            
            # Get selected monsters
            selected_indices = self.allowed_monsters_listbox.curselection()
            monsters = []
            for obj in self.config.get("game_objects", []):
                if obj.get("object_type") == "character":
                    monster = obj.get("monster", False)
                    if isinstance(monster, bool) and monster:
                        monsters.append(obj)
                    elif isinstance(monster, str) and monster.lower() == "true":
                        monsters.append(obj)
                    elif "properties" in obj and obj["properties"].get("monster") == "true":
                        monsters.append(obj)
            
            monsters.sort(key=lambda x: x.get("name", x.get("id", "")))
            allowed_ids = [monsters[i].get("id", "") for i in selected_indices]
            level["allowed_monsters"] = allowed_ids
            
            self.save_config()
        except (ValueError, IndexError):
            pass  # Ignore invalid input while typing
    
    def generate_level_map(self):
        """Generate a map using the currently selected level's configuration"""
        selection = self.level_listbox.curselection()
        if not selection:
            self.log_status("Please select a level first", "error")
            return
        
        index = selection[0]
        levels = self.config.get("levels", [])
        if index >= len(levels):
            self.log_status("Invalid level selection", "error")
            return
        
        level = levels[index]
        
        try:
            self.log_status(f"Generating map for Level {level.get('level_number', 0)}...", "info")
            
            # Make HTTP request to the server's map generation endpoint
            import urllib.request
            import json
            
            # Get level number from selected level
            level_num = level.get("level_number", 0)
            url = f"http://localhost:3000/api/map?level={level_num}"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
            except urllib.error.URLError as e:
                self.log_status(f"Failed to connect to server: {e}. Make sure the server is running.", "error")
                return
            
            # Parse the response
            self.level_map_width = data.get("width", 80)
            self.level_map_height = data.get("height", 50)
            
            # Convert map tiles to tile IDs
            map_tiles = data.get("map", [])
            self.level_map_data = []
            for row in map_tiles:
                tile_row = []
                for tile in row:
                    tile_id = self._find_tile_id_by_properties(tile)
                    tile_row.append(tile_id)
                self.level_map_data.append(tile_row)
            
            # Parse entities (monsters + player)
            entities_data = data.get("entities", [])
            self.level_map_entities = []
            for entity in entities_data:
                self.level_map_entities.append({
                    "x": entity.get("x", 0),
                    "y": entity.get("y", 0),
                    "object_id": entity.get("object_id", ""),
                    "sprite_x": entity.get("sprite_x", 0),
                    "sprite_y": entity.get("sprite_y", 0),
                    "sprite_sheet": entity.get("sprite_sheet"),
                    "controller": entity.get("controller", "AI"),
                })
            
            # Store stairs position
            self.level_map_stairs_position = data.get("stairs_position")
            
            self.render_level_map()
            
            # Show level stats
            num_monsters = sum(1 for e in self.level_map_entities if e.get("controller") == "AI")
            num_players = sum(1 for e in self.level_map_entities if e.get("controller") == "Player")
            level_num = level.get("level_number", 0)
            self.log_status(
                f"Level {level_num} map: {self.level_map_width}x{self.level_map_height}, "
                f"{num_monsters} monsters, {level.get('chest_count', 0)} chests configured", 
                "success"
            )
        except Exception as e:
            self.log_status(f"Failed to generate level map: {e}", "error")
    
    def render_level_map(self):
        """Render the level map on the canvas"""
        if not self.level_map_data:
            return
        
        self.level_map_canvas.delete("all")
        
        # Clear previous sprite image references
        if hasattr(self, '_level_map_sprite_images'):
            self._level_map_sprite_images.clear()
        else:
            self._level_map_sprite_images = []
        
        # Load sprite sheets if needed
        sprite_sheets = {}
        
        # Render each tile
        for y in range(self.level_map_height):
            for x in range(self.level_map_width):
                tile_id = self.level_map_data[y][x]
                
                # Find the tile object
                tile_obj = None
                for obj in self.config.get("game_objects", []):
                    if obj.get("id") == tile_id and obj.get("object_type") == "tile":
                        tile_obj = obj
                        break
                
                if not tile_obj:
                    scaled_size = int(self.tile_size * self.level_map_zoom_level)
                    self.level_map_canvas.create_rectangle(
                        x * scaled_size, y * scaled_size,
                        (x + 1) * scaled_size, (y + 1) * scaled_size,
                        fill="gray", outline="black"
                    )
                    continue
                
                # Get sprite coordinates
                sprites = tile_obj.get("sprites", [])
                if not sprites:
                    sprite_x = tile_obj.get("sprite_x", 0)
                    sprite_y = tile_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = tile_obj.get("sprite_sheet", "tiles.png")
                
                # Load sprite sheet if not already loaded
                if sprite_sheet not in sprite_sheets:
                    sheet_path = self.assets_dir / sprite_sheet
                    if sheet_path.exists():
                        try:
                            img = Image.open(sheet_path)
                            sprite_sheets[sprite_sheet] = img
                        except Exception as e:
                            sprite_sheets[sprite_sheet] = None
                    else:
                        sprite_sheets[sprite_sheet] = None
                
                # Draw the tile
                if sprite_sheets.get(sprite_sheet):
                    img = sprite_sheets[sprite_sheet]
                    left = sprite_x * self.tile_size
                    top = sprite_y * self.tile_size
                    right = left + self.tile_size
                    bottom = top + self.tile_size
                    
                    try:
                        sprite_img = img.crop((left, top, right, bottom))
                        scaled_size = int(self.tile_size * self.level_map_zoom_level)
                        sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_sprite_images.append(sprite_photo)
                        
                        dest_x = x * scaled_size
                        dest_y = y * scaled_size
                        self.level_map_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                    except Exception:
                        scaled_size = int(self.tile_size * self.level_map_zoom_level)
                        self.level_map_canvas.create_rectangle(
                            x * scaled_size, y * scaled_size,
                            (x + 1) * scaled_size, (y + 1) * scaled_size,
                            fill="gray", outline="black"
                        )
                else:
                    scaled_size = int(self.tile_size * self.level_map_zoom_level)
                    self.level_map_canvas.create_rectangle(
                        x * scaled_size, y * scaled_size,
                        (x + 1) * scaled_size, (y + 1) * scaled_size,
                        fill="gray", outline="black"
                    )
        
        # Draw entities (monsters and players)
        for entity in self.level_map_entities:
            x = entity.get("x", 0)
            y = entity.get("y", 0)
            object_id = entity.get("object_id", "")
            controller = entity.get("controller", "AI")
            
            # Find the character object
            char_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("id") == object_id and obj.get("object_type") == "character":
                    char_obj = obj
                    break
            
            if char_obj:
                sprites = char_obj.get("sprites", [])
                if not sprites:
                    sprite_x = char_obj.get("sprite_x", 0)
                    sprite_y = char_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = char_obj.get("sprite_sheet", "tiles.png")
                
                sheet_path = self.assets_dir / sprite_sheet
                if sheet_path.exists():
                    try:
                        img = Image.open(sheet_path)
                        left = sprite_x * self.tile_size
                        top = sprite_y * self.tile_size
                        right = left + self.tile_size
                        bottom = top + self.tile_size
                        
                        sprite_img = img.crop((left, top, right, bottom))
                        scaled_size = int(self.tile_size * self.level_map_zoom_level)
                        sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_sprite_images.append(sprite_photo)
                        
                        dest_x = x * scaled_size
                        dest_y = y * scaled_size
                        self.level_map_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                        
                        # Add colored border: green for player, red for monsters
                        border_color = "green" if controller == "Player" else "red"
                        self.level_map_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + scaled_size, dest_y + scaled_size,
                            outline=border_color, width=max(2, int(3 * self.level_map_zoom_level))
                        )
                    except Exception:
                        pass
        
        # Draw stairs
        if self.level_map_stairs_position:
            stairs_x, stairs_y = self.level_map_stairs_position
            stairs_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("object_type") == "goal":
                    stairs_obj = obj
                    break
            
            if stairs_obj:
                sprites = stairs_obj.get("sprites", [])
                if not sprites:
                    sprite_x = stairs_obj.get("sprite_x", 0)
                    sprite_y = stairs_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = stairs_obj.get("sprite_sheet", "tiles.png")
                
                sheet_path = self.assets_dir / sprite_sheet
                if sheet_path.exists():
                    try:
                        img = Image.open(sheet_path)
                        left = sprite_x * self.tile_size
                        top = sprite_y * self.tile_size
                        right = left + self.tile_size
                        bottom = top + self.tile_size
                        
                        sprite_img = img.crop((left, top, right, bottom))
                        scaled_size = int(self.tile_size * self.level_map_zoom_level)
                        sprite_img = sprite_img.resize((scaled_size, scaled_size), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_sprite_images.append(sprite_photo)
                        
                        dest_x = stairs_x * scaled_size
                        dest_y = stairs_y * scaled_size
                        self.level_map_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                        
                        # Add bright cyan border
                        self.level_map_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + scaled_size, dest_y + scaled_size,
                            outline="cyan", width=max(2, int(3 * self.level_map_zoom_level))
                        )
                    except Exception:
                        pass
        
        # Update scroll region
        self.level_map_canvas.config(scrollregion=self.level_map_canvas.bbox("all"))
    
    def level_map_zoom_in(self):
        """Zoom in on level map"""
        self.level_map_zoom_level = min(self.level_map_zoom_level * 1.2, 5.0)
        self.level_map_zoom_label.config(text=f"Zoom: {int(self.level_map_zoom_level * 100)}%")
        if self.level_map_data:
            self.render_level_map()
    
    def level_map_zoom_out(self):
        """Zoom out on level map"""
        self.level_map_zoom_level = max(self.level_map_zoom_level / 1.2, 0.1)
        self.level_map_zoom_label.config(text=f"Zoom: {int(self.level_map_zoom_level * 100)}%")
        if self.level_map_data:
            self.render_level_map()
    
    def level_map_zoom_reset(self):
        """Reset level map zoom"""
        self.level_map_zoom_level = 1.0
        self.level_map_zoom_label.config(text="Zoom: 100%")
        if self.level_map_data:
            self.render_level_map()
    
    def on_level_map_mousewheel(self, event):
        """Handle mouse wheel for level map zoom"""
        if event.delta > 0:
            self.level_map_zoom_in()
        else:
            self.level_map_zoom_out()
    
    def fullscreen_level_map(self):
        """Open map preview in fullscreen window"""
        if not self.level_map_data:
            self.log_status("Generate a map first", "error")
            return
        
        # Close existing fullscreen window if open
        if self.level_map_fullscreen_window is not None:
            self.level_map_fullscreen_window.destroy()
            self.level_map_fullscreen_window = None
            self.level_map_fullscreen_canvas = None
            return
        
        # Create fullscreen window
        self.level_map_fullscreen_window = tk.Toplevel(self.root)
        self.level_map_fullscreen_window.title("Map Preview - Fullscreen")
        self.level_map_fullscreen_window.attributes("-fullscreen", True)
        self.level_map_fullscreen_window.configure(bg="black")
        
        # Bind Escape to exit fullscreen
        self.level_map_fullscreen_window.bind("<Escape>", lambda e: self.fullscreen_level_map())
        self.level_map_fullscreen_window.bind("<KeyPress-f>", lambda e: self.fullscreen_level_map())
        self.level_map_fullscreen_window.bind("<KeyPress-F>", lambda e: self.fullscreen_level_map())
        
        # Create canvas that fills the window
        self.level_map_fullscreen_canvas = tk.Canvas(
            self.level_map_fullscreen_window, 
            bg="black",
            highlightthickness=0
        )
        self.level_map_fullscreen_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Add zoom controls at the top
        zoom_frame = tk.Frame(self.level_map_fullscreen_window, bg="black")
        zoom_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(zoom_frame, text="Zoom In (+)", command=self.level_map_fullscreen_zoom_in, 
                 bg="gray", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(zoom_frame, text="Zoom Out (-)", command=self.level_map_fullscreen_zoom_out,
                 bg="gray", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(zoom_frame, text="Reset (1x)", command=self.level_map_fullscreen_zoom_reset,
                 bg="gray", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(zoom_frame, text="Exit Fullscreen (Esc/F)", command=self.fullscreen_level_map,
                 bg="red", fg="white", padx=10, pady=5).pack(side=tk.RIGHT, padx=5)
        
        self.level_map_fullscreen_zoom_label = tk.Label(zoom_frame, text="Zoom: 100%", 
                                                        bg="black", fg="white", font=("Arial", 12))
        self.level_map_fullscreen_zoom_label.pack(side=tk.LEFT, padx=20)
        
        # Mouse wheel support
        self.level_map_fullscreen_canvas.bind("<MouseWheel>", self.on_level_map_fullscreen_mousewheel)
        self.level_map_fullscreen_canvas.bind("<Button-4>", lambda e: self.level_map_fullscreen_zoom_in())
        self.level_map_fullscreen_canvas.bind("<Button-5>", lambda e: self.level_map_fullscreen_zoom_out())
        self.level_map_fullscreen_canvas.bind("<Enter>", lambda e: self.level_map_fullscreen_canvas.focus_set())
        
        # Use current zoom level for fullscreen (or keep existing if already set)
        if self.level_map_fullscreen_zoom_level == 1.0:
            self.level_map_fullscreen_zoom_level = self.level_map_zoom_level
        
        # Render the map in fullscreen
        self.render_level_map_fullscreen()
        
        # Focus the fullscreen window
        self.level_map_fullscreen_window.focus_set()
    
    def render_level_map_fullscreen(self):
        """Render the level map on the fullscreen canvas"""
        if not self.level_map_data or not self.level_map_fullscreen_canvas:
            return
        
        self.level_map_fullscreen_canvas.delete("all")
        
        # Clear previous sprite image references
        if hasattr(self, '_level_map_fullscreen_sprite_images'):
            self._level_map_fullscreen_sprite_images.clear()
        else:
            self._level_map_fullscreen_sprite_images = []
        
        # Get window size
        window_width = self.level_map_fullscreen_window.winfo_width()
        window_height = self.level_map_fullscreen_window.winfo_height()
        
        # Calculate optimal zoom to fit map on screen
        if window_width > 1 and window_height > 1:
            tile_size_scaled = int(self.tile_size * self.level_map_fullscreen_zoom_level)
            map_pixel_width = self.level_map_width * tile_size_scaled
            map_pixel_height = self.level_map_height * tile_size_scaled
            
            # Center the map
            offset_x = max(0, (window_width - map_pixel_width) // 2)
            offset_y = max(0, (window_height - map_pixel_height) // 2)
        else:
            offset_x = 0
            offset_y = 0
            tile_size_scaled = int(self.tile_size * self.level_map_fullscreen_zoom_level)
        
        # Load sprite sheets
        sprite_sheets = {}
        
        # Render each tile
        for y in range(self.level_map_height):
            for x in range(self.level_map_width):
                tile_id = self.level_map_data[y][x]
                
                # Find the tile object
                tile_obj = None
                for obj in self.config.get("game_objects", []):
                    if obj.get("id") == tile_id and obj.get("object_type") == "tile":
                        tile_obj = obj
                        break
                
                if not tile_obj:
                    dest_x = offset_x + x * tile_size_scaled
                    dest_y = offset_y + y * tile_size_scaled
                    self.level_map_fullscreen_canvas.create_rectangle(
                        dest_x, dest_y,
                        dest_x + tile_size_scaled, dest_y + tile_size_scaled,
                        fill="gray", outline="black"
                    )
                    continue
                
                # Get sprite coordinates
                sprites = tile_obj.get("sprites", [])
                if not sprites:
                    sprite_x = tile_obj.get("sprite_x", 0)
                    sprite_y = tile_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = tile_obj.get("sprite_sheet", "tiles.png")
                
                # Load sprite sheet if not already loaded
                if sprite_sheet not in sprite_sheets:
                    sheet_path = self.assets_dir / sprite_sheet
                    if sheet_path.exists():
                        try:
                            img = Image.open(sheet_path)
                            sprite_sheets[sprite_sheet] = img
                        except Exception:
                            sprite_sheets[sprite_sheet] = None
                    else:
                        sprite_sheets[sprite_sheet] = None
                
                # Draw the tile
                if sprite_sheets.get(sprite_sheet):
                    img = sprite_sheets[sprite_sheet]
                    left = sprite_x * self.tile_size
                    top = sprite_y * self.tile_size
                    right = left + self.tile_size
                    bottom = top + self.tile_size
                    
                    try:
                        sprite_img = img.crop((left, top, right, bottom))
                        sprite_img = sprite_img.resize((tile_size_scaled, tile_size_scaled), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_fullscreen_sprite_images.append(sprite_photo)
                        
                        dest_x = offset_x + x * tile_size_scaled
                        dest_y = offset_y + y * tile_size_scaled
                        self.level_map_fullscreen_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                    except Exception:
                        dest_x = offset_x + x * tile_size_scaled
                        dest_y = offset_y + y * tile_size_scaled
                        self.level_map_fullscreen_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + tile_size_scaled, dest_y + tile_size_scaled,
                            fill="gray", outline="black"
                        )
                else:
                    dest_x = offset_x + x * tile_size_scaled
                    dest_y = offset_y + y * tile_size_scaled
                    self.level_map_fullscreen_canvas.create_rectangle(
                        dest_x, dest_y,
                        dest_x + tile_size_scaled, dest_y + tile_size_scaled,
                        fill="gray", outline="black"
                    )
        
        # Draw entities
        for entity in self.level_map_entities:
            x = entity.get("x", 0)
            y = entity.get("y", 0)
            object_id = entity.get("object_id", "")
            controller = entity.get("controller", "AI")
            
            char_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("id") == object_id and obj.get("object_type") == "character":
                    char_obj = obj
                    break
            
            if char_obj:
                sprites = char_obj.get("sprites", [])
                if not sprites:
                    sprite_x = char_obj.get("sprite_x", 0)
                    sprite_y = char_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = char_obj.get("sprite_sheet", "tiles.png")
                
                sheet_path = self.assets_dir / sprite_sheet
                if sheet_path.exists():
                    try:
                        img = Image.open(sheet_path)
                        left = sprite_x * self.tile_size
                        top = sprite_y * self.tile_size
                        right = left + self.tile_size
                        bottom = top + self.tile_size
                        
                        sprite_img = img.crop((left, top, right, bottom))
                        sprite_img = sprite_img.resize((tile_size_scaled, tile_size_scaled), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_fullscreen_sprite_images.append(sprite_photo)
                        
                        dest_x = offset_x + x * tile_size_scaled
                        dest_y = offset_y + y * tile_size_scaled
                        self.level_map_fullscreen_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                        
                        border_color = "green" if controller == "Player" else "red"
                        self.level_map_fullscreen_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + tile_size_scaled, dest_y + tile_size_scaled,
                            outline=border_color, width=max(2, int(3 * self.level_map_fullscreen_zoom_level))
                        )
                    except Exception:
                        pass
        
        # Draw stairs
        if self.level_map_stairs_position:
            stairs_x, stairs_y = self.level_map_stairs_position
            stairs_obj = None
            for obj in self.config.get("game_objects", []):
                if obj.get("object_type") == "goal":
                    stairs_obj = obj
                    break
            
            if stairs_obj:
                sprites = stairs_obj.get("sprites", [])
                if not sprites:
                    sprite_x = stairs_obj.get("sprite_x", 0)
                    sprite_y = stairs_obj.get("sprite_y", 0)
                    sprites = [{"x": sprite_x, "y": sprite_y}]
                
                sprite = sprites[0] if sprites else {"x": 0, "y": 0}
                sprite_x = sprite.get("x", 0)
                sprite_y = sprite.get("y", 0)
                sprite_sheet = stairs_obj.get("sprite_sheet", "tiles.png")
                
                sheet_path = self.assets_dir / sprite_sheet
                if sheet_path.exists():
                    try:
                        img = Image.open(sheet_path)
                        left = sprite_x * self.tile_size
                        top = sprite_y * self.tile_size
                        right = left + self.tile_size
                        bottom = top + self.tile_size
                        
                        sprite_img = img.crop((left, top, right, bottom))
                        sprite_img = sprite_img.resize((tile_size_scaled, tile_size_scaled), Image.NEAREST)
                        sprite_photo = ImageTk.PhotoImage(sprite_img)
                        
                        self._level_map_fullscreen_sprite_images.append(sprite_photo)
                        
                        dest_x = offset_x + stairs_x * tile_size_scaled
                        dest_y = offset_y + stairs_y * tile_size_scaled
                        self.level_map_fullscreen_canvas.create_image(
                            dest_x, dest_y,
                            anchor=tk.NW, image=sprite_photo
                        )
                        
                        self.level_map_fullscreen_canvas.create_rectangle(
                            dest_x, dest_y,
                            dest_x + tile_size_scaled, dest_y + tile_size_scaled,
                            outline="cyan", width=max(2, int(3 * self.level_map_fullscreen_zoom_level))
                        )
                    except Exception:
                        pass
    
    def level_map_fullscreen_zoom_in(self):
        """Zoom in on fullscreen map"""
        self.level_map_fullscreen_zoom_level = min(self.level_map_fullscreen_zoom_level * 1.2, 5.0)
        self.level_map_fullscreen_zoom_label.config(text=f"Zoom: {int(self.level_map_fullscreen_zoom_level * 100)}%")
        if self.level_map_data:
            self.render_level_map_fullscreen()
    
    def level_map_fullscreen_zoom_out(self):
        """Zoom out on fullscreen map"""
        self.level_map_fullscreen_zoom_level = max(self.level_map_fullscreen_zoom_level / 1.2, 0.1)
        self.level_map_fullscreen_zoom_label.config(text=f"Zoom: {int(self.level_map_fullscreen_zoom_level * 100)}%")
        if self.level_map_data:
            self.render_level_map_fullscreen()
    
    def level_map_fullscreen_zoom_reset(self):
        """Reset fullscreen map zoom"""
        self.level_map_fullscreen_zoom_level = 1.0
        self.level_map_fullscreen_zoom_label.config(text="Zoom: 100%")
        if self.level_map_data:
            self.render_level_map_fullscreen()
    
    def on_level_map_fullscreen_mousewheel(self, event):
        """Handle mouse wheel for fullscreen map zoom"""
        if event.delta > 0:
            self.level_map_fullscreen_zoom_in()
        else:
            self.level_map_fullscreen_zoom_out()

def main():
    root = tk.Tk()
    app = GameObjectEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()

