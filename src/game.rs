// Re-export everything from the new modules for backward compatibility
pub use crate::message::{GameMessage, PlayerCommand, MessageType, CombatMessage};
pub use crate::entity::{Entity, EntityController};
pub use crate::consumable::Consumable;
pub use crate::chest::Chest;
pub use crate::game_state::GameState;
