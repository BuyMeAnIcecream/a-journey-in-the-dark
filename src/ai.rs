use crate::entity::{Entity, EntityController};
use crate::dungeon::Dungeon;
use crate::message::GameMessage;
use crate::combat::attack_entity;
use crate::consumable::Consumable;
use crate::game_object::GameObjectRegistry;

pub fn process_ai_turns(
    entities: &mut [Entity],
    dungeon: &Dungeon,
    object_registry: &GameObjectRegistry,
    consumables: &mut Vec<Consumable>,
) -> Vec<GameMessage> {
    let mut messages = Vec::new();
    
    // Get all player positions for AI to chase
    let player_positions: Vec<(usize, usize)> = entities
        .iter()
        .filter(|e| e.controller == EntityController::Player && e.is_alive())
        .map(|e| (e.x, e.y))
        .collect();
    
    // Process each AI entity
    let ai_indices: Vec<usize> = entities
        .iter()
        .enumerate()
        .filter(|(_, e)| e.controller == EntityController::AI && e.is_alive())
        .map(|(idx, _)| idx)
        .collect();
    
    for ai_idx in ai_indices {
        let ai_entity = &entities[ai_idx];
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
            // Check if player is adjacent (orthogonal only, no diagonal attacks)
            let dx = target_x as i32 - ai_x as i32;
            let dy = target_y as i32 - ai_y as i32;
            let is_adjacent_orthogonal = (dx.abs() == 1 && dy == 0) || (dx == 0 && dy.abs() == 1);
            
            // If player is orthogonally adjacent, attack directly
            if is_adjacent_orthogonal {
                if let Some(target_idx) = entities.iter().position(|e| {
                    e.x == target_x && 
                    e.y == target_y && 
                    e.is_alive() &&
                    e.controller == EntityController::Player
                }) {
                    // Attack player
                    if let Some(msg) = attack_entity(entities, ai_idx, target_idx, object_registry, consumables) {
                        messages.push(msg);
                    }
                }
            } else {
                // Use pathfinding to find the best move towards player
                if let Some((dx, dy)) = find_path_step(entities, dungeon, ai_x, ai_y, target_x, target_y, ai_idx) {
                    let new_x = (ai_x as i32 + dx) as usize;
                    let new_y = (ai_y as i32 + dy) as usize;
                    
                    // Only move if not attacking (we already checked for adjacent attacks above)
                    move_entity(entities, dungeon, ai_idx, dx, dy);
                }
            }
            // If pathfinding fails, monster stays in place (blocked)
        } else {
            // No player nearby, wander randomly
            let directions = [(0, -1), (0, 1), (-1, 0), (1, 0)];
            use rand::Rng;
            let mut rng = rand::thread_rng();
            let (dx, dy) = directions[rng.gen_range(0..directions.len())];
            
            move_entity(entities, dungeon, ai_idx, dx, dy);
        }
    }
    
    messages
}

// BFS pathfinding to find the next step towards target
pub fn find_path_step(
    entities: &[Entity],
    dungeon: &Dungeon,
    start_x: usize,
    start_y: usize,
    target_x: usize,
    target_y: usize,
    entity_idx: usize,
) -> Option<(i32, i32)> {
    use std::collections::{VecDeque, HashSet, HashMap};
    
    // If already adjacent, return direct move
    let dx = target_x as i32 - start_x as i32;
    let dy = target_y as i32 - start_y as i32;
    
    if dx.abs() <= 1 && dy.abs() <= 1 {
        return Some((dx.signum(), dy.signum()));
    }
    
    // BFS to find path
    let mut queue = VecDeque::new();
    let mut visited = HashSet::new();
    let mut parent = HashMap::new();
    
    queue.push_back((start_x, start_y));
    visited.insert((start_x, start_y));
    
    while let Some((x, y)) = queue.pop_front() {
        if x == target_x && y == target_y {
            // Reconstruct path to find first step
            let mut current = (target_x, target_y);
            let mut path = Vec::new();
            
            while current != (start_x, start_y) {
                path.push(current);
                if let Some(&prev) = parent.get(&current) {
                    current = prev;
                } else {
                    break;
                }
            }
            
            if let Some(&(first_x, first_y)) = path.last() {
                let step_dx = first_x as i32 - start_x as i32;
                let step_dy = first_y as i32 - start_y as i32;
                return Some((step_dx.signum(), step_dy.signum()));
            }
            break;
        }
        
        // Check all 4 directions
        let neighbors = [
            (x.wrapping_sub(1), y),
            (x + 1, y),
            (x, y.wrapping_sub(1)),
            (x, y + 1),
        ];
        
        for (nx, ny) in neighbors.iter() {
            if *nx >= dungeon.width || *ny >= dungeon.height {
                continue;
            }
            
            if visited.contains(&(*nx, *ny)) {
                continue;
            }
            
            // Check if tile is walkable
            if !dungeon.is_walkable(*nx, *ny) {
                continue;
            }
            
            // Check if position is occupied by another entity (except target)
            if entities.iter().any(|e| {
                e.id != entities[entity_idx].id && 
                e.x == *nx && 
                e.y == *ny && 
                e.is_alive() &&
                !(e.x == target_x && e.y == target_y) // Allow target position
            }) {
                continue;
            }
            
            visited.insert((*nx, *ny));
            parent.insert((*nx, *ny), (x, y));
            queue.push_back((*nx, *ny));
        }
    }
    
    // If no path found, try direct movement
    if dx != 0 || dy != 0 {
        Some((dx.signum(), dy.signum()))
    } else {
        None
    }
}

// Helper function to move an entity (extracted from GameState for reuse)
fn move_entity(
    entities: &mut [Entity],
    dungeon: &Dungeon,
    entity_idx: usize,
    dx: i32,
    dy: i32,
) {
    if entity_idx >= entities.len() {
        return;
    }
    
    // Update facing direction based on horizontal movement
    if dx > 0 {
        // Moving right
        entities[entity_idx].facing_right = true;
    } else if dx < 0 {
        // Moving left
        entities[entity_idx].facing_right = false;
    }
    // If dx == 0, keep current facing direction
    
    let entity = &entities[entity_idx];
    let new_x = entity.x as i32 + dx;
    let new_y = entity.y as i32 + dy;
    
    if new_x >= 0 && new_y >= 0 {
        let new_x = new_x as usize;
        let new_y = new_y as usize;
        
        // Check bounds
        if new_x >= dungeon.width || new_y >= dungeon.height {
            return;
        }
        
        // Check if tile is walkable
        if !dungeon.is_walkable(new_x, new_y) {
            return;
        }
        
        // Check if there's another entity at the target position
        if entities.iter().any(|e| e.id != entities[entity_idx].id && e.x == new_x && e.y == new_y && e.is_alive()) {
            return;  // Can't move through other entities
        }
        
        // Move the entity
        entities[entity_idx].x = new_x;
        entities[entity_idx].y = new_y;
    }
}

