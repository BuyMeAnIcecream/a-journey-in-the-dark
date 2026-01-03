use crate::dungeon::{Dungeon, Room};
use crate::tile_registry::TileRegistry;
use crate::game_object_registry::GameObjectRegistry;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CombatMessage {
    pub attacker: String,
    pub target: String,
    pub damage: u32,
    pub target_health_after: u32,
    pub target_died: bool,
}

#[derive(Deserialize)]
pub struct PlayerCommand {
    pub action: String,
    #[serde(default)]
    pub confirm_stairs: Option<bool>,  // Optional confirmation for stairs
    #[serde(default)]
    pub confirm_restart: Option<bool>,  // Optional confirmation for restart after death
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
    pub facing_right: bool,  // true = facing right, false = facing left
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
            facing_right: true,  // Default: facing right
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
    pub stairs_position: Option<(usize, usize)>,  // Position of stairs (goal tile)
    pub player_confirmations: std::collections::HashSet<String>,  // Players who confirmed they want to end level
    pub restart_confirmations: std::collections::HashSet<String>,  // Players who confirmed they want to restart after death
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
        
        let mut entities = Vec::new();
        
        // Don't create a default player entity - players will be added when they connect
        
        // Spawn monsters in each room
        let monster_templates = object_registry.get_monster_characters();
        if !monster_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut monster_id_counter = 0;
            
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
                }
            }
        }
        
        // Place stairs in the room farthest from player spawn
        let stairs_pos = Self::place_stairs(&dungeon, player_x, player_y, &object_registry);
        if stairs_pos.is_some() {
        } else {
        }
        
        Self {
            dungeon,
            entities,
            tile_registry,
            object_registry,
            stairs_position: stairs_pos,
            player_confirmations: std::collections::HashSet::new(),
            restart_confirmations: std::collections::HashSet::new(),
        }
    }
    
    fn place_stairs(
        dungeon: &Dungeon,
        player_x: usize,
        player_y: usize,
        object_registry: &GameObjectRegistry,
    ) -> Option<(usize, usize)> {
        // Find stairs object (should be type "goal" or "item", not "tile")
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
        } else {
        }
        
        None
    }
    
    #[allow(dead_code)]
    pub fn get_player(&self) -> Option<&Entity> {
        self.entities.iter().find(|e| e.controller == EntityController::Player)
    }
    
    #[allow(dead_code)]
    pub fn get_player_mut(&mut self) -> Option<&mut Entity> {
        self.entities.iter_mut().find(|e| e.controller == EntityController::Player)
    }

    pub fn handle_command(&mut self, cmd: &PlayerCommand, player_id: &str) -> (Vec<CombatMessage>, bool, bool) {
        let mut messages = Vec::new();
        let mut level_complete = false;
        let mut restart_confirmed = false;
        
        // Handle restart confirmation if present
        if let Some(true) = cmd.confirm_restart {
            restart_confirmed = self.confirm_restart(player_id);
        }
        
        // Handle stairs confirmation if present
        if let Some(true) = cmd.confirm_stairs {
            level_complete = self.confirm_stairs(player_id);
        }
        
        // Check if all players are dead
        let all_players_dead = self.are_all_players_dead();
        
        // If all players are dead, don't process movement
        if all_players_dead {
            return (messages, level_complete, restart_confirmed);
        }
        
        // Find the specific player entity by ID
        let player_idx = self.entities.iter().position(|e| e.id == player_id && e.controller == EntityController::Player);
        
        if let Some(idx) = player_idx {
            let (dx, dy) = match cmd.action.as_str() {
                "move_up" => (0, -1),
                "move_down" => (0, 1),
                "move_left" => (-1, 0),
                "move_right" => (1, 0),
                _ => {
                    // Still process AI even if player action is invalid
                    messages.extend(self.process_ai_turns());
                    return (messages, level_complete, restart_confirmed);
                },
            };
            
            // Check if there's an enemy at the target position
            let entity = &self.entities[idx];
            let new_x = (entity.x as i32 + dx) as usize;
            let new_y = (entity.y as i32 + dy) as usize;
            
            // Check bounds
            if new_x < self.dungeon.width && new_y < self.dungeon.height {
                // Check if there's an enemy (AI-controlled entity) at target position
                if let Some(target_idx) = self.entities.iter().position(|e| {
                    e.id != entity.id && 
                    e.x == new_x && 
                    e.y == new_y && 
                    e.is_alive() &&
                    e.controller == EntityController::AI
                }) {
                    // Attack instead of moving
                    if let Some(msg) = self.attack_entity(idx, target_idx) {
                        messages.push(msg);
                    }
                } else {
                    // No enemy, try to move
                    self.move_entity(idx, dx, dy);
                    
                    // Check if player stepped on stairs
                    let new_x = self.entities[idx].x;
                    let new_y = self.entities[idx].y;
                    if let Some((stairs_x, stairs_y)) = self.stairs_position {
                        if new_x == stairs_x && new_y == stairs_y {
                            // Player stepped on stairs - they need to confirm
                            // This will be handled by the client showing a confirmation dialog
                            // For now, we just note that the player is on stairs
                        }
                    }
                }
            }
        }
        
        // After player turn, process all AI turns (only if level not complete and not all players dead)
        if !level_complete && !self.are_all_players_dead() {
            messages.extend(self.process_ai_turns());
        }
        
        (messages, level_complete, restart_confirmed)
    }
    
    pub fn are_all_players_dead(&self) -> bool {
        let alive_players = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player && e.is_alive())
            .count();
        alive_players == 0 && self.entities.iter().any(|e| e.controller == EntityController::Player)
    }
    
    pub fn confirm_restart(&mut self, player_id: &str) -> bool {
        // Add player to restart confirmations
        self.restart_confirmations.insert(player_id.to_string());
        
        // Check if all players have confirmed
        let all_players: Vec<String> = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player)
            .map(|e| e.id.clone())
            .collect();
        
        let all_confirmed = !all_players.is_empty() && all_players.iter().all(|pid| self.restart_confirmations.contains(pid));
        
        if all_confirmed {
            // Reset the game state
            self.restart_level();
            return true;
        }
        
        false
    }
    
    pub fn restart_level(&mut self) {
        // Save player IDs before clearing entities
        let player_ids: Vec<String> = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player)
            .map(|e| e.id.clone())
            .collect();
        
        // Clear confirmations
        self.player_confirmations.clear();
        self.restart_confirmations.clear();
        
        // Remove all entities
        self.entities.clear();
        
        // Generate new dungeon
        self.dungeon = Dungeon::new_with_registry(80, 50, &self.tile_registry);
        
        // Find first floor tile for player spawn
        let mut player_x = 1;
        let mut player_y = 1;
        for y in 0..self.dungeon.height {
            for x in 0..self.dungeon.width {
                if self.dungeon.tiles[y][x].walkable {
                    player_x = x;
                    player_y = y;
                    break;
                }
            }
            if self.dungeon.tiles[player_y][player_x].walkable {
                break;
            }
        }
        
        // Re-add all players at the spawn location
        for player_id in player_ids {
            self.add_player(player_id);
        }
        
        // Spawn monsters in each room
        let monster_templates = self.object_registry.get_monster_characters();
        if !monster_templates.is_empty() {
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let mut monster_id_counter = 0;
            
            for room in &self.dungeon.rooms {
                let mut valid_positions = Vec::new();
                for dy in 0..room.height {
                    for dx in 0..room.width {
                        let x = room.x + dx;
                        let y = room.y + dy;
                        if x < self.dungeon.width && y < self.dungeon.height {
                            if self.dungeon.tiles[y][x].walkable {
                                if !(x == player_x && y == player_y) {
                                    let occupied = self.entities.iter().any(|e: &Entity| e.x == x && e.y == y && e.is_alive());
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
                        monster_template.health.unwrap_or(20),
                        EntityController::AI,
                    );
                    self.entities.push(monster);
                    monster_id_counter += 1;
                }
            }
        }
        
        // Place stairs (use first player position for stairs placement)
        let first_player_pos = self.entities.iter()
            .find(|e| e.controller == EntityController::Player)
            .map(|e| (e.x, e.y))
            .unwrap_or((player_x, player_y));
        self.stairs_position = Self::place_stairs(&self.dungeon, first_player_pos.0, first_player_pos.1, &self.object_registry);
    }
    
    pub fn confirm_stairs(&mut self, player_id: &str) -> bool {
        // Add player to confirmations
        self.player_confirmations.insert(player_id.to_string());
        
        // Check if all players have confirmed
        let all_players: Vec<String> = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player && e.is_alive())
            .map(|e| e.id.clone())
            .collect();
        
        let all_confirmed = all_players.iter().all(|pid| self.player_confirmations.contains(pid));
        
        if all_confirmed {
            return true;
        }
        
        false
    }
    
    pub fn add_player(&mut self, player_id: String) -> Option<usize> {
        // Get player object template from registry - must have id "player"
        let player_obj = self.object_registry.get_object("player");
        
        if let Some(player_template) = player_obj {
            // Find spawn position: next to first player if exists, otherwise first walkable tile
            let mut spawn_x = 1;
            let mut spawn_y = 1;
            let mut found = false;
            
            // First, try to find an existing player to spawn next to
            if let Some(first_player) = self.entities.iter().find(|e| e.controller == EntityController::Player && e.is_alive()) {
                // Try to spawn adjacent to the first player
                let adjacent_positions = [
                    (first_player.x.wrapping_sub(1), first_player.y),     // Left
                    (first_player.x + 1, first_player.y),                // Right
                    (first_player.x, first_player.y.wrapping_sub(1)),    // Up
                    (first_player.x, first_player.y + 1),                // Down
                ];
                
                for (x, y) in adjacent_positions.iter() {
                    if *x < self.dungeon.width && *y < self.dungeon.height {
                        if self.dungeon.tiles[*y][*x].walkable {
                            // Check if position is occupied
                            let occupied = self.entities.iter().any(|e: &Entity| e.x == *x && e.y == *y && e.is_alive());
                            if !occupied {
                                spawn_x = *x;
                                spawn_y = *y;
                                found = true;
                                break;
                            }
                        }
                    }
                }
            }
            
            // If we didn't find a spot next to first player, find first available walkable tile
            if !found {
                for y in 0..self.dungeon.height {
                    for x in 0..self.dungeon.width {
                        if self.dungeon.tiles[y][x].walkable {
                            // Check if position is occupied
                            let occupied = self.entities.iter().any(|e: &Entity| e.x == x && e.y == y && e.is_alive());
                            if !occupied {
                                spawn_x = x;
                                spawn_y = y;
                                found = true;
                                break;
                            }
                        }
                    }
                    if found {
                        break;
                    }
                }
            }
            
            let max_health = player_template.health.unwrap_or(100);
            let attack = player_template.attack
                .or_else(|| {
                    player_template.properties
                        .get("attack")
                        .and_then(|s| s.parse::<i32>().ok())
                })
                .unwrap_or(10);
            
            let player = Entity::new(
                player_id,
                spawn_x,
                spawn_y,
                player_template.id.clone(),
                attack,
                max_health,
                EntityController::Player,
            );
            
            let idx = self.entities.len();
            self.entities.push(player);
            Some(idx)
        } else {
            None
        }
    }
    
    pub fn remove_player(&mut self, player_id: &str) {
        // Remove player entity (or mark as dead)
        if let Some(idx) = self.entities.iter().position(|e| e.id == player_id && e.controller == EntityController::Player) {
            self.entities[idx].current_health = 0; // Mark as dead
        }
    }
    
    fn attack_entity(&mut self, attacker_idx: usize, target_idx: usize) -> Option<CombatMessage> {
        if attacker_idx >= self.entities.len() || target_idx >= self.entities.len() {
            return None;
        }
        
        // Get attacker's values before mutable borrow
        let damage = self.entities[attacker_idx].attack.max(0) as u32;
        let attacker_id = self.entities[attacker_idx].id.clone();
        let attacker_x = self.entities[attacker_idx].x;
        
        // Apply damage to target
        let target = &mut self.entities[target_idx];
        let target_id = target.id.clone();
        let target_x = target.x;
        
        if damage >= target.current_health {
            target.current_health = 0;
        } else {
            target.current_health -= damage;
        }
        
        let health_after = target.current_health;
        let target_died = health_after == 0;
        
        // Update attacker's facing direction based on relative position
        if attacker_x < target_x {
            self.entities[attacker_idx].facing_right = true;
        } else if attacker_x > target_x {
            self.entities[attacker_idx].facing_right = false;
        }
        
        Some(CombatMessage {
            attacker: attacker_id,
            target: target_id,
            damage,
            target_health_after: health_after,
            target_died,
        })
    }
    
    fn move_entity(&mut self, entity_idx: usize, dx: i32, dy: i32) {
        if entity_idx >= self.entities.len() {
            return;
        }
        
        // Update facing direction based on horizontal movement
        if dx > 0 {
            // Moving right
            self.entities[entity_idx].facing_right = true;
        } else if dx < 0 {
            // Moving left
            self.entities[entity_idx].facing_right = false;
        }
        // If dx == 0, keep current facing direction
        
        let entity = &self.entities[entity_idx];
        let new_x = entity.x as i32 + dx;
        let new_y = entity.y as i32 + dy;
        
        if new_x >= 0 && new_y >= 0 {
            let new_x = new_x as usize;
            let new_y = new_y as usize;
            
            // Check bounds
            if new_x >= self.dungeon.width || new_y >= self.dungeon.height {
                return;
            }
            
            // Check if tile is walkable
            if !self.dungeon.is_walkable(new_x, new_y) {
                return;
            }
            
            // Check if another entity is at that position (but allow attacking enemies)
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
    
    fn process_ai_turns(&mut self) -> Vec<CombatMessage> {
        let mut messages = Vec::new();
        
        // Get all player positions for AI to chase
        let player_positions: Vec<(usize, usize)> = self.entities
            .iter()
            .filter(|e| e.controller == EntityController::Player && e.is_alive())
            .map(|e| (e.x, e.y))
            .collect();
        
        // Process each AI entity
        let ai_indices: Vec<usize> = self.entities
            .iter()
            .enumerate()
            .filter(|(_, e)| e.controller == EntityController::AI && e.is_alive())
            .map(|(idx, _)| idx)
            .collect();
        
        for ai_idx in ai_indices {
            let ai_entity = &self.entities[ai_idx];
            let ai_x = ai_entity.x;
            let ai_y = ai_entity.y;
            
            // Find nearest player within 5 tile radius
            let mut nearest_player: Option<(usize, usize)> = None;
            let mut min_distance = 6; // 5 + 1 to check if within range
            
            for (px, py) in &player_positions {
                let dx = if ai_x > *px { ai_x - *px } else { *px - ai_x };
                let dy = if ai_y > *py { ai_y - *py } else { *py - ai_y };
                let distance = dx.max(dy); // Chebyshev distance (max of dx, dy)
                
                if distance <= 5 && distance < min_distance {
                    min_distance = distance;
                    nearest_player = Some((*px, *py));
                }
            }
            
            if let Some((target_x, target_y)) = nearest_player {
                // Use pathfinding to find the best move towards player
                if let Some((dx, dy)) = self.find_path_step(ai_x, ai_y, target_x, target_y, ai_idx) {
                    let new_x = (ai_x as i32 + dx) as usize;
                    let new_y = (ai_y as i32 + dy) as usize;
                    
                    // Check if there's a player at target position (attack)
                    if let Some(target_idx) = self.entities.iter().position(|e| {
                        e.x == new_x && 
                        e.y == new_y && 
                        e.is_alive() &&
                        e.controller == EntityController::Player
                    }) {
                        // Attack player
                        if let Some(msg) = self.attack_entity(ai_idx, target_idx) {
                            messages.push(msg);
                        }
                    } else {
                        // Move towards player using pathfinding
                        self.move_entity(ai_idx, dx, dy);
                    }
                }
                // If pathfinding fails, monster stays in place (blocked)
            } else {
                // No player nearby, wander randomly
                let directions = [(0, -1), (0, 1), (-1, 0), (1, 0)];
                use rand::Rng;
                let mut rng = rand::thread_rng();
                let (dx, dy) = directions[rng.gen_range(0..directions.len())];
                
                self.move_entity(ai_idx, dx, dy);
            }
        }
        
        messages
    }
    
    // BFS pathfinding to find the next step towards target
    fn find_path_step(&self, start_x: usize, start_y: usize, target_x: usize, target_y: usize, entity_idx: usize) -> Option<(i32, i32)> {
        use std::collections::{VecDeque, HashSet, HashMap};
        
        // If already adjacent, return direct move
        let dx = target_x as i32 - start_x as i32;
        let dy = target_y as i32 - start_y as i32;
        if dx.abs() <= 1 && dy.abs() <= 1 {
            // Check if direct move is valid
            let check_dx = if dx > 0 { 1 } else if dx < 0 { -1 } else { 0 };
            let check_dy = if dy > 0 { 1 } else if dy < 0 { -1 } else { 0 };
            let check_x = (start_x as i32 + check_dx) as usize;
            let check_y = (start_y as i32 + check_dy) as usize;
            
            if check_x < self.dungeon.width && check_y < self.dungeon.height &&
               self.dungeon.is_walkable(check_x, check_y) {
                // Check if position is occupied by another entity
                let entity_id = &self.entities[entity_idx].id;
                let occupied = self.entities.iter().any(|e| 
                    e.id != *entity_id && e.x == check_x && e.y == check_y && e.is_alive()
                );
                if !occupied {
                    return Some((check_dx, check_dy));
                }
            }
        }
        
        // BFS to find path
        let mut queue = VecDeque::new();
        let mut visited = HashSet::new();
        let mut parent: HashMap<(usize, usize), (usize, usize)> = HashMap::new();
        
        queue.push_back((start_x, start_y));
        visited.insert((start_x, start_y));
        
        let directions = [(0, -1), (0, 1), (-1, 0), (1, 0)];
        let entity_id = &self.entities[entity_idx].id;
        
        while let Some((x, y)) = queue.pop_front() {
            if x == target_x && y == target_y {
                // Reconstruct path to find first step
                let mut current = (x, y);
                let mut path = Vec::new();
                
                while current != (start_x, start_y) {
                    path.push(current);
                    if let Some(&prev) = parent.get(&current) {
                        current = prev;
                    } else {
                        break;
                    }
                }
                
                if let Some(&first_step) = path.last() {
                    let dx = first_step.0 as i32 - start_x as i32;
                    let dy = first_step.1 as i32 - start_y as i32;
                    return Some((dx, dy));
                }
                break;
            }
            
            for &(dx, dy) in &directions {
                let new_x = (x as i32 + dx) as usize;
                let new_y = (y as i32 + dy) as usize;
                
                if new_x >= self.dungeon.width || new_y >= self.dungeon.height {
                    continue;
                }
                
                if !self.dungeon.is_walkable(new_x, new_y) {
                    continue;
                }
                
                // Check if position is occupied by another entity (except target)
                let occupied = self.entities.iter().any(|e| 
                    e.id != *entity_id && 
                    e.x == new_x && 
                    e.y == new_y && 
                    e.is_alive() &&
                    !(e.x == target_x && e.y == target_y) // Allow target position
                );
                if occupied {
                    continue;
                }
                
                if !visited.contains(&(new_x, new_y)) {
                    visited.insert((new_x, new_y));
                    parent.insert((new_x, new_y), (x, y));
                    queue.push_back((new_x, new_y));
                }
            }
        }
        
        None // No path found
    }
}


