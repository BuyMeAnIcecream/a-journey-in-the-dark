use crate::dungeon::Dungeon;
use crate::tile_registry::TileRegistry;
use crate::game_object_registry::GameObjectRegistry;
use serde::Deserialize;

#[derive(Deserialize)]
pub struct PlayerCommand {
    pub action: String,
}

pub struct Player {
    pub x: usize,
    pub y: usize,
    pub object_id: String,  // Reference to GameObject
}

impl Player {
    pub fn new(x: usize, y: usize, object_id: String) -> Self {
        Self { x, y, object_id }
    }
}

pub struct GameState {
    pub dungeon: Dungeon,
    pub player: Player,
    #[allow(dead_code)]
    pub tile_registry: TileRegistry,
    pub object_registry: GameObjectRegistry,
}

impl GameState {
    pub fn new_with_registry(tile_registry: TileRegistry, object_registry: GameObjectRegistry) -> Self {
        let dungeon = Dungeon::new_with_registry(80, 50, &tile_registry);
        
        // Find first floor tile for player spawn
        let mut player_x = 1;
        let mut player_y = 1;
        for y in 0..dungeon.height {
            for x in 0..dungeon.width {
                if dungeon.tiles[y][x].walkable {
                    player_x = x;
                    player_y = y;
                    break;
                }
            }
            if dungeon.tiles[player_y][player_x].walkable {
                break;
            }
        }
        
        // Get player object ID from registry, or use default
        let player_id = object_registry
            .get_objects_by_type("character")
            .first()
            .map(|obj| obj.id.clone())
            .unwrap_or_else(|| "player".to_string());
        
        Self {
            dungeon,
            player: Player::new(player_x, player_y, player_id),
            tile_registry,
            object_registry,
        }
    }

    pub fn handle_command(&mut self, cmd: &PlayerCommand) {
        match cmd.action.as_str() {
            "move_up" => self.move_player(0, -1),
            "move_down" => self.move_player(0, 1),
            "move_left" => self.move_player(-1, 0),
            "move_right" => self.move_player(1, 0),
            _ => {}
        }
    }

    fn move_player(&mut self, dx: i32, dy: i32) {
        let new_x = self.player.x as i32 + dx;
        let new_y = self.player.y as i32 + dy;
        
        if new_x >= 0 && new_y >= 0 {
            let new_x = new_x as usize;
            let new_y = new_y as usize;
            
            if self.dungeon.is_walkable(new_x, new_y) {
                self.player.x = new_x;
                self.player.y = new_y;
            }
        }
    }
}

