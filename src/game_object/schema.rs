use serde::{Serialize, Deserialize};
use std::fs;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct FieldSchema {
    pub name: String,
    pub field_type: String,  // "String", "i32", "u32", "bool", "Option<i32>", "Vec<SpriteCoord>"
    pub optional: bool,
    pub default: Option<String>,  // Default value as string
    pub show_for_types: Vec<String>,  // Empty = show for all, ["character"] = only for characters
    pub label: Option<String>,  // Display label (defaults to capitalized name)
}

#[derive(Serialize, Deserialize, Debug)]
pub struct GameObjectSchema {
    pub fields: Vec<FieldSchema>,
}

impl GameObjectSchema {
    pub fn generate() -> Self {
        let fields = vec![
            FieldSchema {
                name: "id".to_string(),
                field_type: "String".to_string(),
                optional: false,
                default: None,
                show_for_types: vec![],
                label: Some("ID".to_string()),
            },
            FieldSchema {
                name: "name".to_string(),
                field_type: "String".to_string(),
                optional: false,
                default: None,
                show_for_types: vec![],
                label: Some("Name".to_string()),
            },
            FieldSchema {
                name: "object_type".to_string(),
                field_type: "String".to_string(),
                optional: false,
                default: None,
                show_for_types: vec![],
                label: Some("Type".to_string()),
            },
            FieldSchema {
                name: "walkable".to_string(),
                field_type: "bool".to_string(),
                optional: false,
                default: Some("false".to_string()),
                show_for_types: vec!["tile".to_string()],
                label: Some("Walkable".to_string()),
            },
            FieldSchema {
                name: "health".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec!["character".to_string()],
                label: Some("Health".to_string()),
            },
            FieldSchema {
                name: "attack".to_string(),
                field_type: "Option<i32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec!["character".to_string()],
                label: Some("Attack".to_string()),
            },
            FieldSchema {
                name: "defense".to_string(),
                field_type: "Option<i32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec!["character".to_string()],
                label: Some("Defense".to_string()),
            },
            FieldSchema {
                name: "attack_spread_percent".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: Some("20".to_string()),
                show_for_types: vec!["character".to_string()],
                label: Some("Attack Spread %".to_string()),
            },
            FieldSchema {
                name: "crit_chance_percent".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: Some("0".to_string()),
                show_for_types: vec!["character".to_string()],
                label: Some("Crit Chance %".to_string()),
            },
            FieldSchema {
                name: "crit_damage_percent".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: Some("150".to_string()),
                show_for_types: vec!["character".to_string()],
                label: Some("Crit Damage %".to_string()),
            },
            FieldSchema {
                name: "monster".to_string(),
                field_type: "Option<bool>".to_string(),
                optional: true,
                default: Some("false".to_string()),
                show_for_types: vec!["character".to_string()],
                label: Some("Monster".to_string()),
            },
            FieldSchema {
                name: "healing_power".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec!["consumable".to_string()],
                label: Some("Healing Power".to_string()),
            },
            FieldSchema {
                name: "sprites".to_string(),
                field_type: "Vec<SpriteCoord>".to_string(),
                optional: false,
                default: Some("[]".to_string()),
                show_for_types: vec![],
                label: Some("Sprites (Default, or 'before' for interactables)".to_string()),
            },
            FieldSchema {
                name: "interactable".to_string(),
                field_type: "Option<InteractableData>".to_string(),
                optional: true,
                default: Some("None".to_string()),
                show_for_types: vec!["chest".to_string()],
                label: Some("Interactable (before/after states)".to_string()),
            },
            FieldSchema {
                name: "sprite_sheet".to_string(),
                field_type: "Option<String>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec![],
                label: Some("Sprite Sheet".to_string()),
            },
            // Legacy fields - hidden but supported
            FieldSchema {
                name: "sprite_x".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec![],
                label: None,  // Hidden field
            },
            FieldSchema {
                name: "sprite_y".to_string(),
                field_type: "Option<u32>".to_string(),
                optional: true,
                default: None,
                show_for_types: vec![],
                label: None,  // Hidden field
            },
        ];
        
        Self { fields }
    }
    
    pub fn save_to_file(path: &str) -> Result<(), Box<dyn std::error::Error>> {
        let schema = Self::generate();
        let json = serde_json::to_string_pretty(&schema)?;
        fs::write(path, json)?;
        Ok(())
    }
}

