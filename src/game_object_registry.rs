use std::collections::HashMap;
use crate::game_object::GameObject;

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

    pub fn get_objects_by_type(&self, object_type: &str) -> Vec<&GameObject> {
        self.objects
            .values()
            .filter(|obj| obj.object_type == object_type)
            .collect()
    }

    #[allow(dead_code)]
    pub fn get_all_objects(&self) -> Vec<&GameObject> {
        self.objects.values().collect()
    }
}

