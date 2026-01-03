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

class GameObjectEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Object Editor")
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
        
    def create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Left panel - Object list
        left_panel = ttk.Frame(main_frame)
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
        middle_panel = ttk.LabelFrame(main_frame, text="Properties", padding="10")
        middle_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Properties form
        self.prop_vars = {}
        properties = [
            ("ID:", "id", str),
            ("Name:", "name", str),
            ("Type:", "object_type", str),
            ("Walkable:", "walkable", bool),
            ("Health:", "health", int),
            ("Sprite Sheet:", "sprite_sheet", str),
        ]
        
        for i, (label, key, dtype) in enumerate(properties):
            ttk.Label(middle_panel, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            
            if dtype == bool:
                var = tk.BooleanVar()
                widget = ttk.Checkbutton(middle_panel, variable=var)
            elif dtype == int:
                var = tk.StringVar()
                widget = ttk.Entry(middle_panel, textvariable=var, width=20)
            else:
                var = tk.StringVar()
                widget = ttk.Entry(middle_panel, textvariable=var, width=20)
            
            widget.grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
            self.prop_vars[key] = (var, dtype)
        
        # Type dropdown
        type_combo = ttk.Combobox(middle_panel, textvariable=self.prop_vars["object_type"][0], 
                                  values=["tile", "character", "item", "monster"], width=17)
        type_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Sprite sheet dropdown (populated from available sprite sheets)
        sprite_sheet_combo = ttk.Combobox(middle_panel, textvariable=self.prop_vars["sprite_sheet"][0], 
                                          width=17)
        sprite_sheet_combo.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5)
        # Update sprite sheet dropdown when sprite sheets are refreshed
        self.sprite_sheet_prop_combo = sprite_sheet_combo
        
        # Sprite array management
        sprite_row = len(properties)
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
        
        # Note: Save is now handled by the main "Save" button at the bottom
        
        # Store last clicked coordinates for adding sprites
        self.last_clicked_sprite = None
        
        # Right panel - Sprite preview
        right_panel = ttk.LabelFrame(main_frame, text="Sprite Preview", padding="10")
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
        
        # Bottom - Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))
        ttk.Button(button_frame, text="Save", command=self.save_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Restart Server", command=self.restart_server).pack(side=tk.LEFT, padx=5)
        self.server_status_label = ttk.Label(button_frame, text="Server: Unknown", foreground="gray")
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        # Check server status on startup
        self.root.after(1000, self.check_server_status)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
    def load_config(self):
        """Load game config from TOML file"""
        if not self.config_path.exists():
            messagebox.showwarning("Config Not Found", 
                                  f"Config file not found at {self.config_path}\n"
                                  "A default config will be created.")
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
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")
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
            messagebox.showwarning("Sprite Sheet Not Found",
                                  f"Sprite sheet not found at {self.sprite_sheet_path}")
            return
        
        try:
            # Load original image (don't resize)
            self.original_sprite_image = Image.open(self.sprite_sheet_path)
            self.zoom_level = 1.0
            self.update_sprite_display()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sprite sheet: {e}")
    
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
    
    def refresh_object_list(self):
        """Refresh the object listbox"""
        self.object_listbox.delete(0, tk.END)
        if not self.config or "game_objects" not in self.config:
            return
        
        filter_text = self.filter_var.get().lower()
        for obj in self.config["game_objects"]:
            name = obj.get("name", obj.get("id", "Unknown"))
            obj_type = obj.get("object_type", "unknown")
            display_text = f"{name} ({obj_type})"
            if filter_text == "" or filter_text in display_text.lower():
                self.object_listbox.insert(tk.END, display_text)
    
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
        
        obj = self.current_object
        
        # Set standard properties
        for key, (var, dtype) in self.prop_vars.items():
            if key in obj:
                if dtype == bool:
                    var.set(obj[key])
                elif dtype == int:
                    var.set(str(obj.get(key, "")))
                else:
                    var.set(str(obj.get(key, "")))
            else:
                if dtype == bool:
                    var.set(False)
                else:
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
    
    
    def add_sprite_from_click(self):
        """Add sprite from last click or prompt for coordinates"""
        if not self.current_object:
            messagebox.showwarning("No Selection", "Please select an object first")
            return
        
        if self.last_clicked_sprite:
            x, y = self.last_clicked_sprite
            self.sprite_listbox.insert(tk.END, f"({x}, {y})")
            self.last_clicked_sprite = None
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
                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers")
            
            ttk.Button(dialog, text="Add", command=add_sprite).grid(row=2, column=0, columnspan=2, pady=10)
    
    def remove_sprite(self):
        """Remove selected sprite from list"""
        selection = self.sprite_listbox.curselection()
        if selection:
            self.sprite_listbox.delete(selection[0])
    
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
        # Select the new object
        self.object_listbox.selection_set(len(self.config["game_objects"]) - 1)
        self.object_listbox.see(len(self.config["game_objects"]) - 1)
    
    def delete_object(self):
        """Delete selected object"""
        if not self.current_object:
            messagebox.showwarning("No Selection", "Please select an object to delete")
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
                self.custom_props_text.delete(1.0, tk.END)
                self.sprite_listbox.delete(0, tk.END)
                # Automatically save to clean up the file
                self.save_config()
    
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
            messagebox.showinfo("No Selection", "Please select a game object first")
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
            messagebox.showwarning("Out of Bounds", 
                                  f"Coordinates ({tile_x}, {tile_y}) are outside the sprite sheet bounds.\n"
                                  f"Max coordinates: ({max_tiles_x-1}, {max_tiles_y-1})")
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
        elif response is False:
            # Replace all sprites
            self.current_object["sprites"] = [{"x": tile_x, "y": tile_y}]
            # Automatically set sprite_sheet property to current sheet
            self.current_object["sprite_sheet"] = self.current_sprite_sheet
            self.load_object_to_form()  # Refresh the form
        
        # Redraw highlight
        self.highlight_sprite()
        
        # Show feedback
        if response is not None:
            print(f"✓ {'Added' if response else 'Set'} sprite coordinates ({tile_x}, {tile_y}) for '{self.current_object.get('name', 'object')}'")
    
    def save_all(self):
        """Save current object changes and then save config to file"""
        # First, save current object changes if an object is selected
        if self.current_object:
            try:
                self._save_current_object_changes()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save object changes: {e}")
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
            elif key == "sprite_sheet":
                val = var.get().strip()
                if val:
                    self.current_object["sprite_sheet"] = val
                    # Switch to this sprite sheet if it's different
                    if val != self.current_sprite_sheet and val in self.sprite_sheet_combo['values']:
                        self.sprite_sheet_var.set(val)
                        self.on_sprite_sheet_change()
                else:
                    self.current_object.pop("sprite_sheet", None)  # Remove if empty
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
        
        # Remove legacy fields if sprites array exists
        if sprites:
            self.current_object.pop("sprite_x", None)
            self.current_object.pop("sprite_y", None)
        
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
        
        # Refresh the object list to show updated name
        self.refresh_object_list()
    
    def save_object(self):
        """Save current object changes (kept for backward compatibility, now calls save_all)"""
        self.save_all()
    
    def save_config(self):
        """Save config to file with proper formatting"""
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
            
            # Write with proper formatting
            with open(self.config_path, 'w') as f:
                toml.dump(self.config, f)
            
            # Verify the saved file is valid
            try:
                with open(self.config_path, 'r') as f:
                    toml.load(f)  # Validate it can be parsed
            except Exception as e:
                messagebox.showwarning("Warning", f"Config saved but validation failed: {e}")
                return
            
            messagebox.showinfo("Success", f"Config saved to {self.config_path}")
            # Update server status after saving
            self.root.after(500, self.check_server_status)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
    
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
                    messagebox.showerror("Build Error", f"Failed to build server:\n{error_msg}")
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
                    messagebox.showerror("Error", "Failed to stop the server")
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
                    messagebox.showinfo("Success", "Server restarted successfully!")
                else:
                    self.server_status_label.config(text="Server: Failed", foreground="red")
                    messagebox.showerror("Error", "Server process started but may have crashed. Check terminal for errors.")
            else:
                self.server_status_label.config(text="Server: Error", foreground="red")
                messagebox.showerror("Error", "Failed to start the server. Check terminal for errors.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restart server: {e}")
            self.check_server_status()

def main():
    root = tk.Tk()
    app = GameObjectEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()

