use std::collections::HashMap;
use crate::game_object::GameObject;
use crate::tile::Tile;

pub struct TileRegistry {
    objects: HashMap<String, GameObject>,
}

impl TileRegistry {
    pub fn new() -> Self {
        Self {
            objects: HashMap::new(),
        }
    }

    pub fn load_from_config(config: &crate::config::GameConfig) -> Self {
        let mut registry = Self::new();
        for obj in &config.game_objects {
            if obj.object_type == "tile" {
                registry.objects.insert(obj.id.clone(), obj.clone());
            }
        }
        registry
    }

    pub fn get_tile(&self, id: &str) -> Option<Tile> {
        self.objects.get(id).map(|obj| Tile::from(obj))
    }

    #[allow(dead_code)]
    pub fn get_object(&self, id: &str) -> Option<&GameObject> {
        self.objects.get(id)
    }

    pub fn get_all_tiles(&self) -> Vec<&GameObject> {
        self.objects.values().collect()
    }
    
    /// Get all walkable tiles (floors)
    pub fn get_walkable_tiles(&self) -> Vec<Tile> {
        self.objects
            .values()
            .filter(|obj| obj.walkable && obj.object_type == "tile")
            .map(|obj| Tile::from(obj))
            .collect()
    }
    
    /// Get all non-walkable tiles (walls)
    pub fn get_wall_tiles(&self) -> Vec<Tile> {
        self.objects
            .values()
            .filter(|obj| !obj.walkable && obj.object_type == "tile")
            .map(|obj| Tile::from(obj))
            .collect()
    }

    // Fallback methods for backward compatibility
    pub fn get_wall_dirt_top(&self) -> Tile {
        self.get_tile("wall_dirt_top")
            .unwrap_or_else(|| Tile::new(false, 0, 0))
    }

    pub fn get_floor_dark(&self) -> Tile {
        self.get_tile("floor_dark")
            .unwrap_or_else(|| Tile::new(true, 0, 6))
    }

    pub fn get_floor_stone(&self) -> Tile {
        self.get_tile("floor_stone")
            .unwrap_or_else(|| {
                // Fallback: create tile with multiple stone sprites
                use crate::game_object::SpriteCoord;
                Tile::with_sprites(true, vec![
                    SpriteCoord { x: 1, y: 6 },
                    SpriteCoord { x: 2, y: 6 },
                    SpriteCoord { x: 3, y: 6 },
                ])
            })
    }

    // Legacy methods for backward compatibility
    #[allow(dead_code)]
    pub fn get_floor_stone1(&self) -> Tile {
        self.get_floor_stone()  // Use the randomized version
    }

    #[allow(dead_code)]
    pub fn get_floor_stone2(&self) -> Tile {
        self.get_floor_stone()  // Use the randomized version
    }

    #[allow(dead_code)]
    pub fn get_floor_stone3(&self) -> Tile {
        self.get_floor_stone()  // Use the randomized version
    }
}


