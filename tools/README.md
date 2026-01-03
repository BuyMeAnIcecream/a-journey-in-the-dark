# Game Object Editor

A Python GUI tool for viewing and editing game objects (tiles, characters, items, etc.) used by the roguelike game server.

## Features

- **View all game objects** in a searchable list
- **Edit properties** including:
  - ID, Name, Type
  - Walkable (boolean)
  - Health (optional, for entities)
  - Sprite coordinates (X, Y)
  - Custom properties
- **Visual sprite sheet preview** with click-to-set coordinates
- **Add/Delete** game objects
- **Save changes** to `game_config.toml` file

## Installation

### Quick Setup (Recommended)

Run the setup script:
```bash
cd tools
./setup.sh
```

### Manual Setup

1. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

Or install manually:
```bash
pip3 install toml Pillow
```

**Note**: On macOS, you may need to use `python3` and `pip3` instead of `python` and `pip`.

## Usage

Run the editor:
```bash
python3 game_object_editor.py
```

Or make it executable and run directly:
```bash
chmod +x game_object_editor.py
./game_object_editor.py
```

Or use the convenience script:
```bash
./run_editor.sh
```

## How It Works

1. The tool reads `game_config.toml` from the project root
2. If the config doesn't exist, it creates a default one
3. All changes are saved back to `game_config.toml`
4. The Rust server automatically loads this config on startup

## Game Object Properties

- **ID**: Unique identifier (e.g., "wall_dirt_top")
- **Name**: Display name (e.g., "Dirt Wall (Top)")
- **Type**: Object type - "tile", "character", "item", "monster", etc.
- **Walkable**: Whether entities can walk on/through this object
- **Health**: Optional health value (None for tiles, Some(value) for entities)
- **Sprite X/Y**: Coordinates in the sprite sheet (0-indexed tile positions)
- **Custom Properties**: Additional key-value pairs for game-specific data

## Sprite Sheet

- The tool loads `assets/tiles.png` as the sprite sheet
- Click on the sprite sheet to set sprite coordinates for the selected object
- The current sprite is highlighted with a red rectangle
- Assumes 16x16 pixel tiles

## Config File Format

The `game_config.toml` file uses TOML format:

```toml
[[game_objects]]
id = "wall_dirt_top"
name = "Dirt Wall (Top)"
object_type = "tile"
walkable = false
health = null
sprite_x = 0
sprite_y = 0
properties = {}

[[game_objects]]
id = "floor_dark"
name = "Dark Floor"
object_type = "tile"
walkable = true
health = null
sprite_x = 0
sprite_y = 6
properties = {}
```


