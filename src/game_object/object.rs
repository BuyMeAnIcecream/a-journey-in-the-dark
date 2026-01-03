use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct SpriteCoord {
    pub x: u32,
    pub y: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameObject {
    pub id: String,
    pub name: String,
    pub object_type: String,  // "tile", "character", "consumable", "chest", "goal", etc.
    pub walkable: bool,
    pub health: Option<u32>,  // None for tiles, Some(value) for entities
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attack: Option<i32>,  // Attack value for entities
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub defense: Option<i32>,  // Defense value for entities
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attack_spread_percent: Option<u32>,  // Attack damage variance as percentage (e.g., 20 = ±20%)
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub crit_chance_percent: Option<u32>,  // Critical hit chance as percentage (e.g., 15 = 15% chance)
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub crit_damage_percent: Option<u32>,  // Critical hit damage multiplier as percentage (e.g., 150 = 150% damage = 1.5x)
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub monster: Option<bool>,  // Whether this character is a monster
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub healing_power: Option<u32>,  // Healing power for consumables
    #[serde(default)]
    pub sprites: Vec<SpriteCoord>,  // Array of sprite coordinates for randomization (default state, or "before" for interactables)
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interactable: Option<crate::game_object::InteractableData>,  // For interactable objects (chests, doors, etc.) with before/after states
    // Legacy fields for backward compatibility
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sprite_x: Option<u32>,
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sprite_y: Option<u32>,
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sprite_sheet: Option<String>,  // Which sprite sheet to use (e.g., "tiles.png", "rogues.png")
    #[serde(default)]
    pub properties: std::collections::HashMap<String, String>,  // Additional custom properties
}

impl GameObject {
    pub fn new(
        id: String,
        name: String,
        object_type: String,
        walkable: bool,
        sprite_x: u32,
        sprite_y: u32,
    ) -> Self {
        Self {
            id,
            name,
            object_type,
            walkable,
            health: None,
            attack: None,
            defense: None,
            attack_spread_percent: None,
            crit_chance_percent: None,
            crit_damage_percent: None,
            monster: None,
            healing_power: None,
            sprites: vec![SpriteCoord { x: sprite_x, y: sprite_y }],
            interactable: None,
            sprite_x: Some(sprite_x),
            sprite_y: Some(sprite_y),
            sprite_sheet: None,
            properties: std::collections::HashMap::new(),
        }
    }

    pub fn with_sprites(mut self, sprites: Vec<SpriteCoord>) -> Self {
        self.sprites = sprites;
        // Set legacy fields from first sprite for backward compatibility
        if let Some(first) = self.sprites.first() {
            self.sprite_x = Some(first.x);
            self.sprite_y = Some(first.y);
        }
        self
    }

    pub fn get_sprites_vec(&self) -> Vec<SpriteCoord> {
        if !self.sprites.is_empty() {
            self.sprites.clone()
        } else if let (Some(x), Some(y)) = (self.sprite_x, self.sprite_y) {
            // Legacy support: convert old format
            vec![SpriteCoord { x, y }]
        } else {
            vec![]
        }
    }

    pub fn with_health(mut self, health: u32) -> Self {
        self.health = Some(health);
        self
    }
    
    /// Get sprites for interactable state (before=false, after=true).
    /// For interactable objects: sprites[0] = before (closed), sprites[1] = after (open)
    /// Returns default sprites if not interactable or if sprites array is too short.
    pub fn get_interactable_sprites(&self, is_after: bool) -> Vec<SpriteCoord> {
        // Check if this is an interactable object (chest, door, etc.)
        // We check both the interactable marker and object_type for safety
        if self.interactable.is_some() || self.object_type == "chest" {
            let sprites = self.get_sprites_vec();
            if is_after {
                // After state: use sprites[1] if available, fallback to sprites[0]
                if sprites.len() > 1 {
                    vec![sprites[1]]
                } else if !sprites.is_empty() {
                    vec![sprites[0]]  // Fallback to first sprite
                } else {
                    vec![]
                }
            } else {
                // Before state: use sprites[0]
                if !sprites.is_empty() {
                    vec![sprites[0]]
                } else {
                    vec![]
                }
            }
        } else {
            // Not an interactable, return default sprites
            self.get_sprites_vec()
        }
    }
    
    /// Get walkable status for interactable state.
    /// Before state: always false (non-walkable)
    /// After state: always true (walkable)
    /// Returns base walkable if not interactable.
    pub fn get_interactable_walkable(&self, is_after: bool) -> bool {
        // Check if this is an interactable object (chest, door, etc.)
        // We check both the interactable marker and object_type for safety
        if self.interactable.is_some() || self.object_type == "chest" {
            // Interactable objects: before = false, after = true
            is_after
        } else {
            // Not an interactable, return base walkable
            self.walkable
        }
    }

    #[allow(dead_code)]
    pub fn with_property(mut self, key: String, value: String) -> Self {
        self.properties.insert(key, value);
        self
    }
}

