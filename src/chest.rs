use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Chest {
    pub id: String,  // Unique chest ID
    pub x: usize,
    pub y: usize,
    pub object_id: String,  // Reference to GameObject (for closed sprite)
    pub open_object_id: Option<String>,  // Reference to GameObject for open sprite (if different)
    pub is_open: bool,  // Whether the chest is open
}

