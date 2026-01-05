use serde::{Deserialize, Serialize};
use std::fs;
use crate::game_object::GameObject;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct LevelConfig {
    pub level_number: u32,
    pub min_rooms: u32,
    pub max_rooms: u32,
    pub min_monsters_per_room: u32,
    pub max_monsters_per_room: u32,
    pub chest_count: u32,
    pub allowed_monsters: Vec<String>,  // IDs of monster characters that can spawn
}

#[derive(Debug, Deserialize, Serialize)]
pub struct GameConfig {
    pub game_objects: Vec<GameObject>,
    #[serde(default)]
    pub levels: Vec<LevelConfig>,
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

}
