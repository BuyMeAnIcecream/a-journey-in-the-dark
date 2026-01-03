use serde::{Deserialize, Serialize};

/// Marker for interactable game objects (chests, doors, etc.)
/// For interactable objects, sprites[0] = before state (closed), sprites[1] = after state (open)
/// Before state is always non-walkable, after state is always walkable
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct InteractableData {
    // Empty struct - just a marker
    // The actual sprites come from GameObject.sprites[0] and sprites[1]
}

