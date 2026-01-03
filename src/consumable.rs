use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Consumable {
    pub id: String,  // Unique consumable ID
    pub x: usize,
    pub y: usize,
    pub object_id: String,  // Reference to GameObject
}

