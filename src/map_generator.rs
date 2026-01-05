use crate::dungeon::{Dungeon, Room};
use crate::tile_registry::TileRegistry;
use crate::game_object::{GameObject, GameObjectRegistry};
use crate::entity::{Entity, EntityController};
use crate::consumable::Consumable;
use crate::chest::Chest;
use crate::config::LevelConfig;
use std::fs::OpenOptions;
use std::io::Write;

fn log_debug(msg: &str) {
    eprintln!("{}", msg);
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open("server_debug.log")
    {
        let _ = writeln!(file, "{}", msg);
    }
}

pub struct MapGenerator;

impl MapGenerator {
    /// Generate a new game map with all entities, monsters, chests, and stairs placed
    pub fn generate_map(
        tile_registry: &TileRegistry,
        object_registry: &GameObjectRegistry,
        level_config: Option<&LevelConfig>,
    ) -> (Dungeon, Vec<Entity>, Vec<Consumable>, Vec<Chest>, Option<(usize, usize)>) {
        // Use level config for room count, or defaults
        let (min_rooms, max_rooms) = if let Some(level) = level_config {
            log_debug(&format!("[MAP GEN] Using level config: min_rooms={}, max_rooms={}", level.min_rooms, level.max_rooms));
            (level.min_rooms, level.max_rooms)
        } else {
            log_debug("[MAP GEN] No level config, using defaults: min_rooms=8, max_rooms=12");
            (8, 12)  // Default values
        };
        
        let dungeon = Dungeon::new_with_room_count(80, 50, tile_registry, min_rooms, max_rooms);
        log_debug(&format!("[MAP GEN] Generated dungeon with {} rooms", dungeon.rooms.len()));
        
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
        
        let mut entities = Vec::new();
        
        // Don't create a default player entity - players will be added when they connect
        
        // Spawn monsters in each room
        let monster_templates = if let Some(level) = level_config {
            // Filter monsters to only those allowed in this level
            let allowed: std::collections::HashSet<&str> = level.allowed_monsters.iter().map(|s| s.as_str()).collect();
            object_registry.get_monster_characters()
                .into_iter()
                .filter(|obj| allowed.contains(obj.id.as_str()))
                .collect()
        } else {
            // Use all monsters if no level config
            object_registry.get_monster_characters()
        };
        
        if !monster_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut monster_id_counter = 0;
            
            // Get min/max monsters per room from level config
            let (min_monsters, max_monsters) = if let Some(level) = level_config {
                (level.min_monsters_per_room, level.max_monsters_per_room)
            } else {
                (1, 1)  // Default: 1 monster per room
            };
            
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
                                    let occupied = entities.iter().any(|e: &Entity| e.x == x && e.y == y);
                                    if !occupied {
                                        valid_positions.push((x, y));
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Spawn monsters based on level config
                let num_monsters = if !valid_positions.is_empty() {
                    rng.gen_range(min_monsters..=max_monsters) as usize
                } else {
                    0
                };
                
                // Spawn monsters up to the number of valid positions
                let monsters_to_spawn = num_monsters.min(valid_positions.len());
                
                // Shuffle positions to randomize spawn locations
                use rand::seq::SliceRandom;
                let mut shuffled_positions = valid_positions;
                shuffled_positions.shuffle(&mut rng);
                
                for i in 0..monsters_to_spawn {
                    let (monster_x, monster_y) = shuffled_positions[i];
                    
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
                    
                    let defense = monster_template.defense
                        .or_else(|| {
                            monster_template.properties
                                .get("defense")
                                .and_then(|s| s.parse::<i32>().ok())
                        })
                        .unwrap_or(0);
                    
                    let attack_spread = monster_template.attack_spread_percent
                        .or_else(|| {
                            monster_template.properties
                                .get("attack_spread_percent")
                                .and_then(|s| s.parse::<u32>().ok())
                        })
                        .unwrap_or(20);
                    
                    let crit_chance = monster_template.crit_chance_percent
                        .or_else(|| {
                            monster_template.properties
                                .get("crit_chance_percent")
                                .and_then(|s| s.parse::<u32>().ok())
                        })
                        .unwrap_or(0);
                    
                    let crit_damage = monster_template.crit_damage_percent
                        .or_else(|| {
                            monster_template.properties
                                .get("crit_damage_percent")
                                .and_then(|s| s.parse::<u32>().ok())
                        })
                        .unwrap_or(150);  // Default 150% crit damage
                    
                    let monster = Entity::new(
                        format!("monster_{}", monster_id_counter),
                        monster_x,
                        monster_y,
                        monster_template.id.clone(),
                        attack,
                        defense,
                        attack_spread,
                        crit_chance,
                        crit_damage,
                        max_health,
                        EntityController::AI,
                    );
                    entities.push(monster);
                    monster_id_counter += 1;
                }
            }
        }
        
        // Place stairs in the room farthest from player spawn
        let stairs_pos = Self::place_stairs(&dungeon, player_x, player_y, object_registry);
        
        // Don't spawn consumables in rooms - they only drop from monsters and chests
        let consumables = Vec::new();
        
        // Spawn chests based on level config
        let mut chests = Vec::new();
        let chest_templates: Vec<&GameObject> = object_registry.get_all_objects()
            .into_iter()
            .filter(|obj| obj.object_type == "chest")
            .collect();
        
        if !chest_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut chest_id_counter = 0;
            
            // Get target chest count from level config
            let target_chest_count = if let Some(level) = level_config {
                level.chest_count
            } else {
                // Default: 1 chest per room (50% chance)
                (dungeon.rooms.len() as f64 * 0.5) as u32
            };
            
            // Collect all valid chest positions across all rooms
            let mut all_valid_positions = Vec::new();
            for room in &dungeon.rooms {
                // Find all walkable positions within the room
                for dy in 0..room.height {
                    for dx in 0..room.width {
                        let x = room.x + dx;
                        let y = room.y + dy;
                        if x < dungeon.width && y < dungeon.height {
                            if dungeon.tiles[y][x].walkable {
                                // Check if position is not occupied
                                if !(x == player_x && y == player_y) {
                                    let occupied_by_entity = entities.iter().any(|e| e.x == x && e.y == y);
                                    let occupied_by_stairs = stairs_pos.map_or(false, |(sx, sy)| sx == x && sy == y);
                                    let occupied_by_consumable = consumables.iter().any(|c: &Consumable| c.x == x && c.y == y);
                                    if !occupied_by_entity && !occupied_by_stairs && !occupied_by_consumable {
                                        all_valid_positions.push((x, y));
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            // Shuffle and select positions for chests
            use rand::seq::SliceRandom;
            all_valid_positions.shuffle(&mut rng);
            let chests_to_spawn = target_chest_count.min(all_valid_positions.len() as u32) as usize;
            
            for i in 0..chests_to_spawn {
                let (chest_x, chest_y) = all_valid_positions[i];
                let chest_template = chest_templates[rng.gen_range(0..chest_templates.len())];
                
                let chest = Chest {
                    id: format!("chest_{}", chest_id_counter),
                    x: chest_x,
                    y: chest_y,
                    object_id: chest_template.id.clone(),
                    is_open: false,
                };
                chests.push(chest);
                chest_id_counter += 1;
            }
        }
        
        (dungeon, entities, consumables, chests, stairs_pos)
    }
    
    /// Place stairs in the room farthest from player spawn
    pub fn place_stairs(
        dungeon: &Dungeon,
        player_x: usize,
        player_y: usize,
        object_registry: &GameObjectRegistry,
    ) -> Option<(usize, usize)> {
        // Find stairs object (should be type "goal", not "tile")
        let stairs_obj = object_registry.get_object("stairs");
        if stairs_obj.is_none() {
            return None;
        }
        
        // Verify it's not a tile type
        let obj = stairs_obj.unwrap();
        if obj.object_type == "tile" {
        }
        
        // Find the room farthest from player spawn
        let mut farthest_room: Option<&Room> = None;
        let mut max_distance = 0;
        
        for room in &dungeon.rooms {
            // Calculate distance from player to room center
            let room_center_x = room.x + room.width / 2;
            let room_center_y = room.y + room.height / 2;
            
            // Use Manhattan distance
            let dx = if player_x > room_center_x { player_x - room_center_x } else { room_center_x - player_x };
            let dy = if player_y > room_center_y { player_y - room_center_y } else { room_center_y - player_y };
            let distance = dx + dy;
            
            if distance > max_distance {
                max_distance = distance;
                farthest_room = Some(room);
            }
        }
        
        if let Some(room) = farthest_room {
            // Find a walkable position in the center of the farthest room
            let center_x = room.x + room.width / 2;
            let center_y = room.y + room.height / 2;
            
            // Try center first, then search nearby
            for offset in 0..=5 {  // Increased search radius
                for dy in -(offset as i32)..=(offset as i32) {
                    for dx in -(offset as i32)..=(offset as i32) {
                        let x = (center_x as i32 + dx) as usize;
                        let y = (center_y as i32 + dy) as usize;
                        
                        if x < dungeon.width && y < dungeon.height {
                            if dungeon.tiles[y][x].walkable {
                                // Don't replace the tile - just return the position
                                // The stairs will be rendered as an entity/object on top
                                return Some((x, y));
                            }
                        }
                    }
                }
            }
        }
        
        None
    }
    
    /// Spawn monsters in all rooms (for restart_level)
    pub fn spawn_monsters(
        dungeon: &Dungeon,
        entities: &mut Vec<Entity>,
        object_registry: &GameObjectRegistry,
        player_x: usize,
        player_y: usize,
    ) {
        let monster_templates = object_registry.get_monster_characters();
        if !monster_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut monster_id_counter = 0;
            
            for room in &dungeon.rooms {
                let mut valid_positions = Vec::new();
                for dy in 0..room.height {
                    for dx in 0..room.width {
                        let x = room.x + dx;
                        let y = room.y + dy;
                        if x < dungeon.width && y < dungeon.height {
                            if dungeon.tiles[y][x].walkable {
                                if !(x == player_x && y == player_y) {
                                    let occupied = entities.iter().any(|e: &Entity| e.x == x && e.y == y && e.is_alive());
                                    if !occupied {
                                        valid_positions.push((x, y));
                                    }
                                }
                            }
                        }
                    }
                }
                
                if !valid_positions.is_empty() {
                    let (monster_x, monster_y) = valid_positions[rng.gen_range(0..valid_positions.len())];
                    let monster_template = &monster_templates[rng.gen_range(0..monster_templates.len())];
                    
                    let monster = Entity::new(
                        format!("monster_{}", monster_id_counter),
                        monster_x,
                        monster_y,
                        monster_template.id.clone(),
                        monster_template.attack.unwrap_or(5) as i32,
                        monster_template.defense.unwrap_or(0) as i32,
                        monster_template.attack_spread_percent.unwrap_or(20),
                        monster_template.crit_chance_percent.unwrap_or(0),
                        monster_template.crit_damage_percent.unwrap_or(150),
                        monster_template.health.unwrap_or(20),
                        EntityController::AI,
                    );
                    entities.push(monster);
                    monster_id_counter += 1;
                }
            }
        }
    }
    
    /// Spawn chests in rooms (for restart_level)
    pub fn spawn_chests(
        dungeon: &Dungeon,
        entities: &[Entity],
        chests: &mut Vec<Chest>,
        object_registry: &GameObjectRegistry,
        player_x: usize,
        player_y: usize,
        stairs_pos: Option<(usize, usize)>,
    ) {
        let chest_templates: Vec<&GameObject> = object_registry.get_all_objects()
            .into_iter()
            .filter(|obj| obj.object_type == "chest")
            .collect();
        
        if !chest_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut chest_id_counter = 0;
            
            // Spawn 1 chest per room (50% chance)
            for room in &dungeon.rooms {
                if rng.gen_bool(0.5) {
                    let mut valid_positions = Vec::new();
                    for dy in 0..room.height {
                        for dx in 0..room.width {
                            let x = room.x + dx;
                            let y = room.y + dy;
                            if x < dungeon.width && y < dungeon.height {
                                if dungeon.tiles[y][x].walkable {
                                    if !(x == player_x && y == player_y) {
                                        let occupied_by_entity = entities.iter().any(|e| e.x == x && e.y == y);
                                        let occupied_by_stairs = stairs_pos.map_or(false, |(sx, sy)| sx == x && sy == y);
                                        let occupied_by_chest = chests.iter().any(|c: &Chest| c.x == x && c.y == y);
                                        if !occupied_by_entity && !occupied_by_stairs && !occupied_by_chest {
                                            valid_positions.push((x, y));
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    if !valid_positions.is_empty() {
                        let pos_idx = rng.gen_range(0..valid_positions.len());
                        let (chest_x, chest_y) = valid_positions[pos_idx];
                        let chest_template = chest_templates[rng.gen_range(0..chest_templates.len())];
                        
                        let chest = Chest {
                            id: format!("chest_{}", chest_id_counter),
                            x: chest_x,
                            y: chest_y,
                            object_id: chest_template.id.clone(),
                            is_open: false,  // Always spawn closed
                        };
                        chests.push(chest);
                        chest_id_counter += 1;
                    }
                }
            }
        }
    }
}

