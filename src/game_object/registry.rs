use std::collections::HashMap;
use crate::game_object::object::GameObject;

pub struct GameObjectRegistry {
    objects: HashMap<String, GameObject>,
}

impl GameObjectRegistry {
    pub fn new() -> Self {
        Self {
            objects: HashMap::new(),
        }
    }

    pub fn load_from_config(config: &crate::config::GameConfig) -> Self {
        let mut registry = Self::new();
        for obj in &config.game_objects {
            registry.objects.insert(obj.id.clone(), obj.clone());
        }
        registry
    }

    pub fn get_object(&self, id: &str) -> Option<&GameObject> {
        self.objects.get(id)
    }

    pub fn get_all_objects(&self) -> Vec<&GameObject> {
        self.objects.values().collect()
    }
    
    /// Get all monster characters (characters with monster=true)
    pub fn get_monster_characters(&self) -> Vec<&GameObject> {
        self.objects
            .values()
            .filter(|obj| {
                obj.object_type == "character" && {
                    // Check if monster is true (top-level field or in properties map)
                    obj.monster.unwrap_or(false) ||
                    obj.properties.get("monster")
                        .map(|s| s == "true")
                        .unwrap_or(false)
                }
            })
            .collect()
    }
}

