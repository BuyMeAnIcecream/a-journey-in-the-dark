use crate::dungeon::Dungeon;
use crate::tile_registry::TileRegistry;
use crate::game_object_registry::GameObjectRegistry;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
pub struct PlayerCommand {
    pub action: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum EntityController {
    Player,
    AI,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Entity {
    pub id: String,  // Unique entity ID
    pub x: usize,
    pub y: usize,
    pub object_id: String,  // Reference to GameObject
    pub attack: i32,
    pub max_health: u32,
    pub current_health: u32,
    pub controller: EntityController,
}

impl Entity {
    pub fn new(
        id: String,
        x: usize,
        y: usize,
        object_id: String,
        attack: i32,
        max_health: u32,
        controller: EntityController,
    ) -> Self {
        Self {
            id,
            x,
            y,
            object_id,
            attack,
            max_health,
            current_health: max_health,
            controller,
        }
    }
    
    pub fn is_alive(&self) -> bool {
        self.current_health > 0
    }
    
    #[allow(dead_code)]
    pub fn take_damage(&mut self, damage: u32) {
        if damage >= self.current_health {
            self.current_health = 0;
        } else {
            self.current_health -= damage;
        }
    }
    
    #[allow(dead_code)]
    pub fn heal(&mut self, amount: u32) {
        self.current_health = (self.current_health + amount).min(self.max_health);
    }
}

pub struct GameState {
    pub dungeon: Dungeon,
    pub entities: Vec<Entity>,  // All entities (player + AI)
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
        let player_obj = object_registry
            .get_objects_by_type("character")
            .first()
            .copied()
            .or_else(|| object_registry.get_object("player"));
        
        let mut entities = Vec::new();
        
        // Create player entity
        if let Some(player_template) = player_obj {
            let max_health = player_template.health.unwrap_or(100);
            let attack = player_template.attack
                .or_else(|| {
                    player_template.properties
                        .get("attack")
                        .and_then(|s| s.parse::<i32>().ok())
                })
                .unwrap_or(10);
            
            println!("Creating player entity: id={}, sprite_sheet={:?}, sprites={:?}", 
                player_template.id, 
                player_template.sprite_sheet,
                player_template.get_sprites_vec());
            
            let player = Entity::new(
                "player".to_string(),
                player_x,
                player_y,
                player_template.id.clone(),
                attack,
                max_health,
                EntityController::Player,
            );
            entities.push(player);
            println!("Player spawned at ({}, {})", player_x, player_y);
        } else {
            println!("WARNING: No player object found in registry!");
        }
        
        // Spawn monsters in each room
        let monster_templates = object_registry.get_monster_characters();
        println!("Found {} monster templates", monster_templates.len());
        if !monster_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut monster_id_counter = 0;
            
            println!("Spawning monsters in {} rooms", dungeon.rooms.len());
            for room in &dungeon.rooms {
                // Find a random walkable position within the room
                let mut valid_positions = Vec::new();
                for dy in 0..room.height {
                    for dx in 0..room.width {
                        let x = room.x + dx;
                        let y = room.y + dy;
                        if x < dungeon.width && y < dungeon.height {
                            if dungeon.tiles[y][x].walkable {
                                // Check if position is not occupied by player
                                if !(x == player_x && y == player_y) {
                                    // Check if position is not occupied by another entity
                                    let occupied = entities.iter().any(|e| e.x == x && e.y == y);
                                    if !occupied {
                                        valid_positions.push((x, y));
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Spawn one monster if we have valid positions
                if !valid_positions.is_empty() {
                    let pos_idx = rng.gen_range(0..valid_positions.len());
                    let (monster_x, monster_y) = valid_positions[pos_idx];
                    
                    // Select a random monster template
                    let monster_template = monster_templates[rng.gen_range(0..monster_templates.len())];
                    
                    let max_health = monster_template.health.unwrap_or(50);
                    // Attack can be top-level field or in properties map
                    let attack = monster_template.attack
                        .or_else(|| {
                            monster_template.properties
                                .get("attack")
                                .and_then(|s| s.parse::<i32>().ok())
                        })
                        .unwrap_or(5);
                    
                    let monster = Entity::new(
                        format!("monster_{}", monster_id_counter),
                        monster_x,
                        monster_y,
                        monster_template.id.clone(),
                        attack,
                        max_health,
                        EntityController::AI,
                    );
                    entities.push(monster);
                    monster_id_counter += 1;
                    println!("Spawned monster {} at ({}, {})", monster_template.id, monster_x, monster_y);
                }
            }
            println!("Total monsters spawned: {}", monster_id_counter);
        }
        
        println!("Total entities created: {} (player + monsters)", entities.len());
        Self {
            dungeon,
            entities,
            tile_registry,
            object_registry,
        }
    }
    
    #[allow(dead_code)]
    pub fn get_player(&self) -> Option<&Entity> {
        self.entities.iter().find(|e| e.controller == EntityController::Player)
    }
    
    #[allow(dead_code)]
    pub fn get_player_mut(&mut self) -> Option<&mut Entity> {
        self.entities.iter_mut().find(|e| e.controller == EntityController::Player)
    }

    pub fn handle_command(&mut self, cmd: &PlayerCommand) {
        // Find player entity index
        let player_idx = self.entities.iter().position(|e| e.controller == EntityController::Player);
        
        if let Some(idx) = player_idx {
            let (dx, dy) = match cmd.action.as_str() {
                "move_up" => (0, -1),
                "move_down" => (0, 1),
                "move_left" => (-1, 0),
                "move_right" => (1, 0),
                _ => return,
            };
            
            self.move_entity(idx, dx, dy);
        }
    }
    
    fn move_entity(&mut self, entity_idx: usize, dx: i32, dy: i32) {
        if entity_idx >= self.entities.len() {
            return;
        }
        
        let entity = &self.entities[entity_idx];
        let new_x = entity.x as i32 + dx;
        let new_y = entity.y as i32 + dy;
        
        if new_x >= 0 && new_y >= 0 {
            let new_x = new_x as usize;
            let new_y = new_y as usize;
            
            // Check if tile is walkable
            if !self.dungeon.is_walkable(new_x, new_y) {
                return;
            }
            
            // Check if another entity is at that position
            let entity_id = self.entities[entity_idx].id.clone();
            let occupied = self.entities.iter().any(|e| e.id != entity_id && e.x == new_x && e.y == new_y && e.is_alive());
            if occupied {
                return;
            }
            
            // Move the entity
            self.entities[entity_idx].x = new_x;
            self.entities[entity_idx].y = new_y;
        }
    }
    
    #[allow(dead_code)]
    pub fn update_ai(&mut self) {
        // TODO: Implement AI behavior
        // For now, AI entities don't move
    }
}


