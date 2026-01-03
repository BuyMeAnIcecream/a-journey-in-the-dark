// Game object module - contains all game object related code
pub mod object;
pub mod registry;
pub mod schema;

// Re-export commonly used types
pub use object::{GameObject, SpriteCoord};
pub use registry::GameObjectRegistry;
pub use schema::{GameObjectSchema, FieldSchema};

