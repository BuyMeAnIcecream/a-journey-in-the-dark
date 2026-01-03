use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Chest {
    pub id: String,  // Unique chest ID
    pub x: usize,
    pub y: usize,
    pub object_id: String,  // Reference to GameObject (which contains interactable data with before/after states)
    pub is_open: bool,  // Whether the chest is open
}

