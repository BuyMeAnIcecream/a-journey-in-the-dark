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
    pub object_type: String,  // "tile", "character", "item", etc.
    pub walkable: bool,
    pub health: Option<u32>,  // None for tiles, Some(value) for entities
    #[serde(default)]
    pub sprites: Vec<SpriteCoord>,  // Array of sprite coordinates for randomization
    // Legacy fields for backward compatibility
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sprite_x: Option<u32>,
    #[serde(default)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sprite_y: Option<u32>,
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
            sprites: vec![SpriteCoord { x: sprite_x, y: sprite_y }],
            sprite_x: Some(sprite_x),
            sprite_y: Some(sprite_y),
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

    #[allow(dead_code)]
    pub fn with_property(mut self, key: String, value: String) -> Self {
        self.properties.insert(key, value);
        self
    }
}


