use serde::{Deserialize, Serialize};
use crate::game_object::{GameObject, SpriteCoord};
use rand::Rng;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Tile {
    pub walkable: bool,
    pub sprite_x: u32,  // X coordinate in sprite sheet (in tiles) - selected sprite
    pub sprite_y: u32,  // Y coordinate in sprite sheet (in tiles) - selected sprite
    #[serde(default)]
    pub sprites: Vec<SpriteCoord>,  // All possible sprites for randomization
}

impl From<&GameObject> for Tile {
    fn from(obj: &GameObject) -> Self {
        let sprites = obj.get_sprites_vec();
        // Select a random sprite from the array
        let selected = if !sprites.is_empty() {
            let mut rng = rand::thread_rng();
            sprites[rng.gen_range(0..sprites.len())]  // Copy trait allows this
        } else {
            // Fallback to legacy fields or default
            SpriteCoord {
                x: obj.sprite_x.unwrap_or(0),
                y: obj.sprite_y.unwrap_or(0),
            }
        };
        
        Self {
            walkable: obj.walkable,
            sprite_x: selected.x,
            sprite_y: selected.y,
            sprites,
        }
    }
}

impl Tile {
    pub fn new(walkable: bool, sprite_x: u32, sprite_y: u32) -> Self {
        Self {
            walkable,
            sprite_x,
            sprite_y,
            sprites: vec![SpriteCoord { x: sprite_x, y: sprite_y }],
        }
    }

    pub fn with_sprites(walkable: bool, sprites: Vec<SpriteCoord>) -> Self {
        let selected = if !sprites.is_empty() {
            let mut rng = rand::thread_rng();
            let idx = rng.gen_range(0..sprites.len());
            sprites[idx]  // Copy trait allows this
        } else {
            SpriteCoord { x: 0, y: 0 }
        };
        
        Self {
            walkable,
            sprite_x: selected.x,
            sprite_y: selected.y,
            sprites,
        }
    }

    pub fn randomize_sprite(&mut self) {
        if !self.sprites.is_empty() {
            let mut rng = rand::thread_rng();
            let idx = rng.gen_range(0..self.sprites.len());
            let selected = &self.sprites[idx];
            self.sprite_x = selected.x;
            self.sprite_y = selected.y;
        }
    }

    // Legacy tile constructors - kept for potential future use
    #[allow(dead_code)]
    pub fn wall_dirt_top() -> Self {
        Self::new(false, 0, 0)  // 1.a
    }

    #[allow(dead_code)]
    pub fn wall_dirt_side() -> Self {
        Self::new(false, 1, 0)  // 1.b
    }

    #[allow(dead_code)]
    pub fn wall_inner() -> Self {
        Self::new(false, 2, 0)  // 1.c
    }

    #[allow(dead_code)]
    pub fn wall_stone_top() -> Self {
        Self::new(false, 0, 1)  // 2.a
    }

    #[allow(dead_code)]
    pub fn wall_stone_side() -> Self {
        Self::new(false, 1, 1)  // 2.b
    }

    #[allow(dead_code)]
    pub fn floor_dark() -> Self {
        Self::new(true, 0, 6)  // 7.a - blank floor (dark grey)
    }

    #[allow(dead_code)]
    pub fn floor_stone1() -> Self {
        Self::new(true, 1, 6)  // 7.b
    }

    #[allow(dead_code)]
    pub fn floor_stone2() -> Self {
        Self::new(true, 2, 6)  // 7.c
    }

    #[allow(dead_code)]
    pub fn floor_stone3() -> Self {
        Self::new(true, 3, 6)  // 7.d
    }

    #[allow(dead_code)]
    pub fn door_closed() -> Self {
        Self::new(false, 0, 16)  // 17.a
    }

    #[allow(dead_code)]
    pub fn door_open() -> Self {
        Self::new(true, 1, 16)  // 17.b
    }
}

