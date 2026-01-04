use crate::dungeon::Dungeon;
use crate::tile_registry::TileRegistry;
use crate::game_object::GameObjectRegistry;
use crate::entity::{Entity, EntityController};
use crate::consumable::Consumable;
use crate::chest::Chest;
use crate::message::{GameMessage, PlayerCommand};
use crate::map_generator::MapGenerator;
use crate::combat::attack_entity;
use crate::ai::process_ai_turns;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TurnPhase {
    PlayerPhase,  // Players are taking their turns
    AIPhase,      // AI entities are taking their turns
}

pub struct GameState {
    pub dungeon: Dungeon,
    pub entities: Vec<Entity>,  // All entities (player + AI)
    pub consumables: Vec<Consumable>,  // All consumables on the map
    pub chests: Vec<Chest>,  // All chests on the map
    pub tile_registry: TileRegistry,
    pub object_registry: GameObjectRegistry,
    pub stairs_position: Option<(usize, usize)>,  // Position of stairs (goal tile)
    pub player_confirmations: std::collections::HashSet<String>,  // Players who confirmed they want to end level
    pub restart_confirmations: std::collections::HashSet<String>,  // Players who confirmed they want to restart after death
    pub turn_phase: TurnPhase,  // Current phase of the turn
    pub players_acted_this_turn: std::collections::HashSet<String>,  // Players who have taken their turn this round
    pub current_turn: u32,  // Current turn number
}

impl GameState {
    pub fn new_with_registry(tile_registry: TileRegistry, object_registry: GameObjectRegistry) -> Self {
        let (dungeon, entities, consumables, chests, stairs_pos) = 
            MapGenerator::generate_map(&tile_registry, &object_registry);
        
        Self {
            dungeon,
            entities,
            consumables,
            chests,
            tile_registry,
            object_registry,
            stairs_position: stairs_pos,
            player_confirmations: std::collections::HashSet::new(),
            restart_confirmations: std::collections::HashSet::new(),
            turn_phase: TurnPhase::PlayerPhase,
            players_acted_this_turn: std::collections::HashSet::new(),
            current_turn: 1,
        }
    }

    pub fn handle_command(&mut self, cmd: &PlayerCommand, player_id: &str) -> (Vec<GameMessage>, bool, bool) {
        let mut messages = Vec::new();
        let mut level_complete = false;
        let mut restart_confirmed = false;
        
        // Check if all players are dead
        let all_players_dead = self.are_all_players_dead();
        
        // If all players are dead, automatically restart the level
        if all_players_dead {
            self.restart_level();
            messages.push(GameMessage::level_event("All players died! Level restarted.".to_string()));
            return (messages, level_complete, restart_confirmed);
        }
        
        // Handle restart confirmation if present (allowed outside of turn)
        if let Some(true) = cmd.confirm_restart {
            if let Some(msg) = self.confirm_restart(player_id) {
                messages.push(msg);
                restart_confirmed = true;
            }
            return (messages, level_complete, restart_confirmed);
        }
        
        // Handle stairs confirmation if present (allowed outside of turn)
        if let Some(true) = cmd.confirm_stairs {
            if let Some(msg) = self.confirm_stairs(player_id) {
                messages.push(msg);
                level_complete = true;
            }
            return (messages, level_complete, restart_confirmed);
        }
        
        // For movement commands, check if it's the player's turn and they haven't acted yet
        // Check if it's the player's turn and they haven't acted yet
        if self.turn_phase != TurnPhase::PlayerPhase {
            // Not player phase, ignore movement commands
            return (messages, level_complete, restart_confirmed);
        }
        
        // Check if this player has already taken their turn
        if self.players_acted_this_turn.contains(player_id) {
            // Player already acted this turn, ignore command
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
                    messages.extend(process_ai_turns(&mut self.entities, &self.dungeon, &self.object_registry, &mut self.consumables));
                    return (messages, level_complete, restart_confirmed);
                },
            };
            
            // Check if there's an enemy at the target position
            let entity = &self.entities[idx];
            let new_x = (entity.x as i32 + dx) as usize;
            let new_y = (entity.y as i32 + dy) as usize;
            
            // Check bounds
            if new_x < self.dungeon.width && new_y < self.dungeon.height {
                // Check if there's a closed chest at target position (highest priority)
                if let Some(chest_idx) = self.chests.iter().position(|c| c.x == new_x && c.y == new_y && !c.is_open) {
                    // Open chest instead of moving
                    let chest = &mut self.chests[chest_idx];
                    chest.is_open = true;
                    
                    // Spawn a potion at the chest location
                    let potion_templates: Vec<&crate::game_object::GameObject> = self.object_registry.get_all_objects()
                        .into_iter()
                        .filter(|obj| obj.object_type == "consumable")
                        .collect();
                    
                    if !potion_templates.is_empty() {
                        use rand::Rng;
                        let mut rng = rand::thread_rng();
                        let potion_template = potion_templates[rng.gen_range(0..potion_templates.len())];
                        
                        use std::sync::atomic::{AtomicU64, Ordering};
                        static CONSUMABLE_COUNTER: AtomicU64 = AtomicU64::new(0);
                        let consumable_id = format!("consumable_{}", CONSUMABLE_COUNTER.fetch_add(1, Ordering::Relaxed));
                        
                        let consumable = Consumable {
                            id: consumable_id,
                            x: new_x,
                            y: new_y,
                            object_id: potion_template.id.clone(),
                        };
                        
                        self.consumables.push(consumable);
                        messages.push(GameMessage::level_event("Chest opened!".to_string()));
                    }
                }
                // Check if there's an enemy (AI-controlled entity) at target position
                else if let Some(target_idx) = self.entities.iter().position(|e| {
                    e.id != entity.id && 
                    e.x == new_x && 
                    e.y == new_y && 
                    e.is_alive() &&
                    e.controller == EntityController::AI
                }) {
                    // Attack instead of moving
                    if let Some(msg) = attack_entity(&mut self.entities, idx, target_idx, &self.object_registry, &mut self.consumables) {
                        messages.push(msg);
                    }
                } else {
                    // No enemy or closed chest, try to move
                    // Check if there's a chest and if it's walkable in its current state
                    let can_move = if let Some(chest) = self.chests.iter().find(|c| c.x == new_x && c.y == new_y) {
                        // Check if chest is walkable in its current state
                        if let Some(chest_obj) = self.object_registry.get_object(&chest.object_id) {
                            chest_obj.get_interactable_walkable(chest.is_open)
                        } else {
                            // Chest object not found, default to not walkable if closed
                            chest.is_open
                        }
                    } else {
                        // No chest at this position, can move
                        true
                    };
                    
                    if can_move {
                        self.move_entity(idx, dx, dy);
                    }
                    
                    // Check if player stepped on a consumable
                    let new_x = self.entities[idx].x;
                    let new_y = self.entities[idx].y;
                    if let Some(consumable_idx) = self.consumables.iter().position(|c| c.x == new_x && c.y == new_y) {
                        // Player stepped on a consumable - consume it
                        let consumable = &self.consumables[consumable_idx];
                        if let Some(consumable_obj) = self.object_registry.get_object(&consumable.object_id) {
                            if let Some(healing_power) = consumable_obj.healing_power {
                                // Heal the player
                                let old_health = self.entities[idx].current_health;
                                self.entities[idx].heal(healing_power);
                                let new_health = self.entities[idx].current_health;
                                let healed_amount = new_health - old_health;
                                
                                // Create a healing message
                                messages.push(GameMessage::healing(
                                    consumable_obj.name.clone(),
                                    self.entities[idx].id.clone(),
                                    healed_amount,
                                    new_health,
                                ));
                                
                                // Remove the consumable
                                self.consumables.remove(consumable_idx);
                            }
                        }
                    }
                    
                    // Check if player stepped on stairs
                    if let Some((stairs_x, stairs_y)) = self.stairs_position {
                        if new_x == stairs_x && new_y == stairs_y {
                            // Player stepped on stairs - they need to confirm
                            // This will be handled by the client showing a confirmation dialog
                            // For now, we just note that the player is on stairs
                        }
                    }
                }
            }
            
            // Mark this player as having acted this turn (after any action: move, attack, or chest open)
            self.players_acted_this_turn.insert(player_id.to_string());
            
            // Check if all alive players have taken their turn
            let alive_players: Vec<String> = self.entities.iter()
                .filter(|e| e.controller == EntityController::Player && e.is_alive())
                .map(|e| e.id.clone())
                .collect();
            
            let all_players_acted = !alive_players.is_empty() && 
                alive_players.iter().all(|pid| self.players_acted_this_turn.contains(pid));
            
            if all_players_acted {
                // All players have acted, now process AI turns
                self.turn_phase = TurnPhase::AIPhase;
                
                if !level_complete && !self.are_all_players_dead() {
                    messages.extend(process_ai_turns(&mut self.entities, &self.dungeon, &self.object_registry, &mut self.consumables));
                }
                
                // Start next turn
                self.turn_phase = TurnPhase::PlayerPhase;
                self.players_acted_this_turn.clear();
                self.current_turn += 1;
            }
        }
        
        (messages, level_complete, restart_confirmed)
    }
    
    pub fn are_all_players_dead(&self) -> bool {
        let alive_players = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player && e.is_alive())
            .count();
        alive_players == 0 && self.entities.iter().any(|e| e.controller == EntityController::Player)
    }
    
    pub fn confirm_restart(&mut self, player_id: &str) -> Option<GameMessage> {
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
            return Some(GameMessage::level_event("Level restarted!".to_string()));
        }
        
        None
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
        
        // Reset turn system
        self.turn_phase = TurnPhase::PlayerPhase;
        self.players_acted_this_turn.clear();
        self.current_turn = 1;
        
        // Remove all entities, consumables, and chests
        self.entities.clear();
        self.consumables.clear();
        self.chests.clear();
        
        // Generate completely new map (dungeon, monsters, chests, consumables, stairs)
        let (dungeon, mut new_entities, new_consumables, new_chests, stairs_pos) = 
            MapGenerator::generate_map(&self.tile_registry, &self.object_registry);
        
        self.dungeon = dungeon;
        self.consumables = new_consumables;
        self.chests = new_chests;
        self.stairs_position = stairs_pos;
        
        // Find first player spawn position (from newly generated map)
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
            // Find spawn position next to first player if exists
            let spawn_pos = if let Some(first_player) = self.entities.iter()
                .find(|e| e.controller == EntityController::Player) {
                // Try to spawn adjacent to the first player
                let adjacent_positions = [
                    (first_player.x.wrapping_sub(1), first_player.y),
                    (first_player.x + 1, first_player.y),
                    (first_player.x, first_player.y.wrapping_sub(1)),
                    (first_player.x, first_player.y + 1),
                ];
                
                let mut found = false;
                let mut spawn_x = player_x;
                let mut spawn_y = player_y;
                
                for (x, y) in adjacent_positions.iter() {
                    if *x < self.dungeon.width && *y < self.dungeon.height {
                        if self.dungeon.tiles[*y][*x].walkable {
                            let occupied = self.entities.iter().any(|e| e.x == *x && e.y == *y);
                            if !occupied {
                                spawn_x = *x;
                                spawn_y = *y;
                                found = true;
                                break;
                            }
                        }
                    }
                }
                
                if found {
                    (spawn_x, spawn_y)
                } else {
                    (player_x, player_y)
                }
            } else {
                (player_x, player_y)
            };
            
            // Add player at spawn position
            if let Some(player_template) = self.object_registry.get_object("player") {
                use crate::entity::Entity;
                let player_entity = Entity::new(
                    player_id.clone(),
                    spawn_pos.0,
                    spawn_pos.1,
                    "player".to_string(),
                    player_template.attack.unwrap_or(10),
                    player_template.defense.unwrap_or(0),
                    player_template.attack_spread_percent.unwrap_or(20),
                    player_template.crit_chance_percent.unwrap_or(0),
                    player_template.crit_damage_percent.unwrap_or(150),
                    player_template.health.unwrap_or(100),
                    EntityController::Player,
                );
                self.entities.push(player_entity);
            }
        }
        
        // Add the monsters from the generated map
        self.entities.extend(new_entities);
    }
    
    pub fn confirm_stairs(&mut self, player_id: &str) -> Option<GameMessage> {
        // Add player to confirmations
        self.player_confirmations.insert(player_id.to_string());
        
        // Check if all players have confirmed
        let all_players: Vec<String> = self.entities.iter()
            .filter(|e| e.controller == EntityController::Player && e.is_alive())
            .map(|e| e.id.clone())
            .collect();
        
        let all_confirmed = all_players.iter().all(|pid| self.player_confirmations.contains(pid));
        
        if all_confirmed {
            return Some(GameMessage::level_event("Level complete! All players confirmed. Preparing next level...".to_string()));
        }
        
        None
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
            
            let defense = player_template.defense
                .or_else(|| {
                    player_template.properties
                        .get("defense")
                        .and_then(|s| s.parse::<i32>().ok())
                })
                .unwrap_or(0);
            
            let attack_spread = player_template.attack_spread_percent
                .or_else(|| {
                    player_template.properties
                        .get("attack_spread_percent")
                        .and_then(|s| s.parse::<u32>().ok())
                })
                .unwrap_or(20);
            
            let crit_chance = player_template.crit_chance_percent
                .or_else(|| {
                    player_template.properties
                        .get("crit_chance_percent")
                        .and_then(|s| s.parse::<u32>().ok())
                })
                .unwrap_or(0);
            
            let crit_damage = player_template.crit_damage_percent
                .or_else(|| {
                    player_template.properties
                        .get("crit_damage_percent")
                        .and_then(|s| s.parse::<u32>().ok())
                })
                .unwrap_or(150);  // Default 150% crit damage
            
            let player = Entity::new(
                player_id,
                spawn_x,
                spawn_y,
                player_template.id.clone(),
                attack,
                defense,
                attack_spread,
                crit_chance,
                crit_damage,
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
        // Remove player entity completely from the game
        self.entities.retain(|e| !(e.id == player_id && e.controller == EntityController::Player));
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
}

