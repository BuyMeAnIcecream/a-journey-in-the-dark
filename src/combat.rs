use crate::entity::{Entity, EntityController};
use crate::consumable::Consumable;
use crate::game_object::GameObjectRegistry;
use crate::message::{GameMessage, CombatMessage};

pub fn attack_entity(
    entities: &mut [Entity],
    attacker_idx: usize,
    target_idx: usize,
    object_registry: &GameObjectRegistry,
    consumables: &mut Vec<Consumable>,
) -> Option<CombatMessage> {
    if attacker_idx >= entities.len() || target_idx >= entities.len() {
        return None;
    }
    
    // Get attacker's values before mutable borrow
    let attacker_attack = entities[attacker_idx].attack;
    let attacker_spread = entities[attacker_idx].attack_spread_percent;
    let attacker_crit_chance = entities[attacker_idx].crit_chance_percent;
    let attacker_crit_damage = entities[attacker_idx].crit_damage_percent;
    let attacker_id = entities[attacker_idx].id.clone();
    let attacker_x = entities[attacker_idx].x;
    
    // Get target's defense
    let target_defense = entities[target_idx].defense;
    
    // Calculate base damage with variance
    // Apply percentage spread: base_attack * (1 ± spread_percent/100)
    use rand::Rng;
    let mut rng = rand::thread_rng();
    let spread_amount = if attacker_spread > 0 {
        // Calculate spread range: ±spread_percent% of base attack
        let spread_range = (attacker_attack as f32 * attacker_spread as f32 / 100.0) as i32;
        // Random value between -spread_range and +spread_range
        rng.gen_range(-spread_range..=spread_range)
    } else {
        0
    };
    
    let base_damage = attacker_attack + spread_amount;
    
    // Check for critical hit
    let is_crit = attacker_crit_chance > 0 && rng.gen_range(0..100) < attacker_crit_chance;
    let final_base_damage = if is_crit {
        // Apply crit damage multiplier: base_damage * (crit_damage_percent / 100)
        (base_damage as f32 * attacker_crit_damage as f32 / 100.0) as i32
    } else {
        base_damage
    };
    
    // Calculate final damage: final_base_damage - defense, minimum 1
    let raw_damage = final_base_damage - target_defense;
    let damage = raw_damage.max(1) as u32;  // Minimum 1 damage
    
    // Get target position before mutable borrow
    let target_y = entities[target_idx].y;
    
    // Apply damage to target
    let target = &mut entities[target_idx];
    let target_id = target.id.clone();
    let target_x = target.x;
    
    if damage >= target.current_health {
        target.current_health = 0;
    } else {
        target.current_health -= damage;
    }
    
    let health_after = target.current_health;
    let target_died = health_after == 0;
    let was_monster = target.controller == EntityController::AI;
    
    // If target died and it was a monster, check for potion drop (25% chance)
    if target_died && was_monster {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        if rng.gen_range(0..100) < 25 {
            // 25% chance to drop a potion
            // Find a health potion template
            let potion_templates: Vec<&crate::game_object::GameObject> = object_registry.get_all_objects()
                .into_iter()
                .filter(|obj| obj.object_type == "consumable")
                .collect();
            
            if !potion_templates.is_empty() {
                // Use first available potion template (or random if multiple)
                let potion_template = potion_templates[rng.gen_range(0..potion_templates.len())];
                
                // Create consumable at the monster's death location
                use std::sync::atomic::{AtomicU64, Ordering};
                static CONSUMABLE_COUNTER: AtomicU64 = AtomicU64::new(0);
                let consumable_id = format!("consumable_{}", CONSUMABLE_COUNTER.fetch_add(1, Ordering::Relaxed));
                
                let consumable = Consumable {
                    id: consumable_id,
                    x: target_x,
                    y: target_y,
                    object_id: potion_template.id.clone(),
                };
                
                consumables.push(consumable);
            }
        }
    }
    
    // Update attacker's facing direction based on relative position
    if attacker_x < target_x {
        entities[attacker_idx].facing_right = true;
    } else if attacker_x > target_x {
        entities[attacker_idx].facing_right = false;
    }
    
    // Get attacker and target names for better message display
    let attacker_name = object_registry.get_object(&entities[attacker_idx].object_id)
        .map(|o| o.name.clone())
        .unwrap_or_else(|| attacker_id.clone());
    let target_name = object_registry.get_object(&entities[target_idx].object_id)
        .map(|o| o.name.clone())
        .unwrap_or_else(|| target_id.clone());
    
    // Create combat message with crit indicator
    let message = if is_crit {
        GameMessage::combat_crit(
            attacker_name,
            target_name,
            damage,
            health_after,
            target_died,
        )
    } else {
        GameMessage::combat(
            attacker_name,
            target_name,
            damage,
            health_after,
            target_died,
        )
    };
    Some(message)
}

