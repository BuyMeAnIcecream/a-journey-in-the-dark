# Roguelike Game Server

A Rust-based roguelike game server with sprite-based rendering in the browser. The server handles all game logic and state updates, while the client renders the game using sprites.

## Features

- **Dungeon Generation**: Procedurally generates roguelike dungeons with rooms and corridors
- **WebSocket Communication**: Real-time bidirectional communication between server and client
- **Sprite Rendering**: Browser-based rendering using canvas and sprites
- **Server-Side Game Logic**: All game updates happen on the server for consistency
- **GameObject System**: Flexible object system for tiles, characters, items, and more
- **Config-Based**: Game objects defined in `game_config.toml` (no code changes needed)
- **Python Editor Tool**: GUI tool to view and edit game objects visually

## Requirements

- Rust (latest stable version)
- A modern web browser
- Python 3 (for the game object editor tool, optional)

## Installation

1. Clone the repository
2. Build the project:
```bash
cargo build --release
```

## Running

Start the server:
```bash
cargo run
```

The server will start on `http://localhost:3000`. Open this URL in your browser to play.

## Controls

- **Arrow Keys** or **WASD**: Move the player character
- The player (green square) can move on floor tiles (dark gray)
- Walls (darker gray) block movement

## Architecture

### Server (Rust)

- `src/main.rs`: Web server setup, WebSocket handling, and routing
- `src/dungeon.rs`: Dungeon generation algorithm (room-based with corridors)
- `src/game.rs`: Game state management and player movement logic
- `src/game_object.rs`: GameObject struct with properties (walkable, health, sprite coordinates)
- `src/tile.rs`: Tile struct (converted from GameObject)
- `src/tile_registry.rs`: Registry for loading tiles from config
- `src/config.rs`: Config file loading/saving (TOML format)

### Client (Browser)

- `client/index.html`: HTML page with embedded JavaScript for rendering and WebSocket communication
- Uses HTML5 Canvas for sprite-based rendering
- Loads sprite sheet from `/assets/tiles.png`

### Development Tools

- `tools/game_object_editor.py`: Python GUI tool for editing game objects
  - View and edit all game objects
  - Set sprite coordinates visually
  - Modify properties (walkable, health, etc.)
  - See `tools/README.md` for details

## Game Object System

The game uses a flexible GameObject system where all objects (tiles, characters, items, etc.) are defined in `game_config.toml`. Each object has:

- **ID**: Unique identifier
- **Name**: Display name
- **Type**: Object type (tile, character, item, monster, etc.)
- **Walkable**: Whether entities can walk on/through it
- **Health**: Optional health value (for entities)
- **Sprite X/Y**: Coordinates in the sprite sheet
- **Properties**: Custom key-value pairs

### Editing Game Objects

Use the Python editor tool:

```bash
cd tools
pip3 install -r requirements.txt
python3 game_object_editor.py
```

Or use the shell script:
```bash
./tools/run_editor.sh
```

**Note**: On macOS, use `python3` and `pip3` instead of `python` and `pip`.

The editor allows you to:
- View all game objects in a searchable list
- Edit properties (walkable, health, sprite coordinates)
- Click on the sprite sheet to set coordinates visually
- Add/delete game objects
- Save changes to `game_config.toml`

The server automatically loads `game_config.toml` on startup. If it doesn't exist, a default config is created.

## Config File

The `game_config.toml` file defines all game objects. Example:

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

## Future Enhancements

- Multiple players support
- Monsters and combat
- Items and inventory
- Fog of war
- Different dungeon generation algorithms
- Save/load game state
- Character sprites and animations

