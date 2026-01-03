use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum MessageType {
    Combat,
    LevelEvent,
    System,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct GameMessage {
    pub message_type: MessageType,
    pub text: String,  // Pre-formatted message text
    // Optional structured data for client-side formatting if needed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attacker: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub damage: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_health_after: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_died: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_crit: Option<bool>,
}

// Helper functions to create messages
impl GameMessage {
    pub fn combat(attacker: String, target: String, damage: u32, health_after: u32, died: bool) -> Self {
        let text = if died {
            format!("{} killed {}!", attacker, target)
        } else {
            format!("{} dealt {} damage to {}", attacker, damage, target)
        };
        
        Self {
            message_type: MessageType::Combat,
            text,
            attacker: Some(attacker),
            target: Some(target),
            damage: Some(damage),
            target_health_after: Some(health_after),
            target_died: Some(died),
            is_crit: Some(false),
        }
    }
    
    pub fn combat_crit(attacker: String, target: String, damage: u32, health_after: u32, died: bool) -> Self {
        let text = if died {
            format!("{} CRITICALLY killed {}!", attacker, target)
        } else {
            format!("{} CRITICALLY dealt {} damage to {}", attacker, damage, target)
        };
        
        Self {
            message_type: MessageType::Combat,
            text,
            attacker: Some(attacker),
            target: Some(target),
            damage: Some(damage),
            target_health_after: Some(health_after),
            target_died: Some(died),
            is_crit: Some(true),
        }
    }
    
    pub fn healing(item: String, target: String, amount: u32, health_after: u32) -> Self {
        let text = format!("{} healed {} for {} HP", item, target, amount);
        
        Self {
            message_type: MessageType::Combat,  // Healing is combat-related
            text,
            attacker: Some(item),
            target: Some(target),
            damage: Some(amount),
            target_health_after: Some(health_after),
            target_died: Some(false),
            is_crit: None,
        }
    }
    
    pub fn level_event(text: String) -> Self {
        Self {
            message_type: MessageType::LevelEvent,
            text,
            attacker: None,
            target: None,
            damage: None,
            target_health_after: None,
            target_died: None,
            is_crit: None,
        }
    }
    
    pub fn system(text: String) -> Self {
        Self {
            message_type: MessageType::System,
            text,
            attacker: None,
            target: None,
            damage: None,
            target_health_after: None,
            target_died: None,
            is_crit: None,
        }
    }
}

// Legacy alias for backward compatibility during transition
pub type CombatMessage = GameMessage;

#[derive(Deserialize)]
pub struct PlayerCommand {
    pub action: String,
    #[serde(default)]
    pub confirm_stairs: Option<bool>,  // Optional confirmation for stairs
    #[serde(default)]
    pub confirm_restart: Option<bool>,  // Optional confirmation for restart after death
}

