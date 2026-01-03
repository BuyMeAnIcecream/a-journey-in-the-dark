use serde::{Deserialize, Serialize};
use std::fs;
use crate::game_object::GameObject;

#[derive(Debug, Deserialize, Serialize)]
pub struct GameConfig {
    pub game_objects: Vec<GameObject>,
}

impl GameConfig {
    pub fn load(path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let config: GameConfig = toml::from_str(&content)?;
        Ok(config)
    }

    pub fn save(&self, path: &str) -> Result<(), Box<dyn std::error::Error>> {
        let content = toml::to_string(self)?;
        fs::write(path, content)?;
        Ok(())
    }

    #[allow(dead_code)]
    pub fn get_object_by_id(&self, id: &str) -> Option<&GameObject> {
        self.game_objects.iter().find(|obj| obj.id == id)
    }

    #[allow(dead_code)]
    pub fn get_objects_by_type(&self, object_type: &str) -> Vec<&GameObject> {
        self.game_objects
            .iter()
            .filter(|obj| obj.object_type == object_type)
            .collect()
    }
}

