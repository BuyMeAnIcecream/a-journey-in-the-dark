use serde::{Deserialize, Serialize};

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
    pub defense: i32,
    pub attack_spread_percent: u32,  // Attack damage variance as percentage (0 = no variance)
    pub crit_chance_percent: u32,  // Critical hit chance as percentage (0 = no crits)
    pub crit_damage_percent: u32,  // Critical hit damage multiplier as percentage (100 = normal damage, 150 = 1.5x)
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
        defense: i32,
        attack_spread_percent: u32,
        crit_chance_percent: u32,
        crit_damage_percent: u32,
        max_health: u32,
        controller: EntityController,
    ) -> Self {
        Self {
            id,
            x,
            y,
            object_id,
            attack,
            defense,
            attack_spread_percent,
            crit_chance_percent,
            crit_damage_percent,
            max_health,
            current_health: max_health,
            controller,
            facing_right: true,  // Default: facing right
        }
    }
    
    pub fn is_alive(&self) -> bool {
        self.current_health > 0
    }
    
    pub fn heal(&mut self, amount: u32) {
        self.current_health = (self.current_health + amount).min(self.max_health);
    }
}

