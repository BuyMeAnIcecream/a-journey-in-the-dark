use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    response::{Html, Json, Response},
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;
use std::fs::OpenOptions;
use std::io::Write;

fn log_debug(msg: &str) {
    eprintln!("{}", msg);
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open("server_debug.log")
    {
        let _ = writeln!(file, "{}", msg);
    }
}

use crate::game_state::GameState;
use crate::message::{GameMessage, PlayerCommand};
use crate::entity::EntityController;
use crate::game_object::schema;

pub type SharedState = Arc<Mutex<GameState>>;
pub type Tx = broadcast::Sender<String>;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct EntityData {
    pub id: String,
    pub object_id: String,  // Reference to GameObject (e.g., "orc", "player")
    pub x: usize,
    pub y: usize,
    pub sprite_x: u32,
    pub sprite_y: u32,
    pub sprite_sheet: Option<String>,
    pub controller: EntityController,
    pub current_health: u32,
    pub max_health: u32,
    pub attack: i32,
    pub defense: i32,
    pub crit_chance_percent: u32,
    pub crit_damage_percent: u32,
    pub facing_right: bool,  // true = facing right, false = facing left (needs mirroring)
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ConsumableData {
    pub id: String,
    pub object_id: String,
    pub x: usize,
    pub y: usize,
    pub sprite_x: u32,
    pub sprite_y: u32,
    pub sprite_sheet: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ChestData {
    pub id: String,
    pub object_id: String,  // Closed chest sprite
    pub open_object_id: Option<String>,  // Open chest sprite (if different)
    pub x: usize,
    pub y: usize,
    pub sprite_x: u32,
    pub sprite_y: u32,
    pub open_sprite_x: u32,
    pub open_sprite_y: u32,
    pub sprite_sheet: Option<String>,
    pub is_open: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct PlayerData {
    pub id: String,
    pub name: String,  // Display name (from GameObject or player_id)
    pub is_alive: bool,
    pub has_acted_this_turn: bool,  // Whether this player has taken their turn this round
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct GameUpdate {
    pub map: Vec<Vec<crate::tile::Tile>>,
    pub entities: Vec<EntityData>,  // All entities (player + AI)
    pub consumables: Vec<ConsumableData>,  // All consumables on the map
    pub chests: Vec<ChestData>,  // All chests on the map
    pub players: Vec<PlayerData>,  // List of all players
    pub current_player_id: Option<String>,  // ID of the current player (for highlighting)
    pub width: usize,
    pub height: usize,
    pub messages: Vec<GameMessage>,  // Game messages (combat, level events, system)
    pub stairs_position: Option<(usize, usize)>,  // Position of stairs (goal)
    pub on_stairs: bool,  // Whether the current player is on stairs
    pub level_complete: bool,  // Whether level is complete (all players confirmed)
    pub all_players_dead: bool,  // Whether all players are dead
    pub restart_confirmed: bool,  // Whether all players confirmed restart
    pub turn_phase: String,  // Current turn phase: "player" or "ai"
    pub current_turn: u32,  // Current turn number
    pub is_my_turn: bool,  // Whether it's the current player's turn (they haven't acted yet)
}

/// Convert GameState to GameUpdate for a specific player
pub fn game_state_to_update(
    game: &GameState,
    player_id: Option<&str>,
) -> GameUpdate {
    // Convert entities to EntityData
    let entities: Vec<EntityData> = game.entities.iter()
        .filter(|e| e.is_alive())  // Only send alive entities
        .map(|entity| {
            let obj = game.object_registry.get_object(&entity.object_id);
            let (sprite_x, sprite_y) = obj
                .and_then(|o| o.get_sprites_vec().first().map(|s| (s.x, s.y)))
                .unwrap_or((0, 0));
            let sprite_sheet = obj.and_then(|o| o.sprite_sheet.clone());
            
            EntityData {
                id: entity.id.clone(),
                object_id: entity.object_id.clone(),
                x: entity.x,
                y: entity.y,
                sprite_x,
                sprite_y,
                sprite_sheet,
                controller: entity.controller,
                current_health: entity.current_health,
                max_health: entity.max_health,
                attack: entity.attack,
                defense: entity.defense,
                crit_chance_percent: entity.crit_chance_percent,
                crit_damage_percent: entity.crit_damage_percent,
                facing_right: entity.facing_right,
            }
        })
        .collect();
    
    // Convert consumables to ConsumableData
    let consumables: Vec<ConsumableData> = game.consumables.iter()
        .map(|consumable| {
            let obj = game.object_registry.get_object(&consumable.object_id);
            let (sprite_x, sprite_y) = obj
                .and_then(|o| o.get_sprites_vec().first().map(|s| (s.x, s.y)))
                .unwrap_or((0, 0));
            let sprite_sheet = obj.and_then(|o| o.sprite_sheet.clone());
            
            ConsumableData {
                id: consumable.id.clone(),
                object_id: consumable.object_id.clone(),
                x: consumable.x,
                y: consumable.y,
                sprite_x,
                sprite_y,
                sprite_sheet,
            }
        })
        .collect();
    
    // Convert chests to ChestData
    let chests: Vec<ChestData> = game.chests.iter()
        .map(|chest| {
            // Get chest object
            let chest_obj = game.object_registry.get_object(&chest.object_id);
            
            // Get before (closed) sprite coordinates
            let (sprite_x, sprite_y) = if let Some(obj) = chest_obj {
                let before_sprites = obj.get_interactable_sprites(false);
                if let Some(sprite) = before_sprites.first() {
                    eprintln!("[CHEST] Chest {} at ({}, {}): closed sprite = ({}, {}), is_open = {}", 
                        chest.id, chest.x, chest.y, sprite.x, sprite.y, chest.is_open);
                    (sprite.x, sprite.y)
                } else {
                    eprintln!("WARNING: Chest object '{}' has no sprites for before state at ({}, {})", 
                        chest.object_id, chest.x, chest.y);
                    (0, 0)
                }
            } else {
                eprintln!("WARNING: Chest object '{}' not found for chest at ({}, {})", 
                    chest.object_id, chest.x, chest.y);
                (0, 0)
            };
            
            // Get after (open) sprite coordinates
            let (open_sprite_x, open_sprite_y) = if let Some(obj) = chest_obj {
                let after_sprites = obj.get_interactable_sprites(true);
                if let Some(sprite) = after_sprites.first() {
                    (sprite.x, sprite.y)
                } else {
                    eprintln!("WARNING: Chest object '{}' has no sprites for after state at ({}, {}), using before sprite", 
                        chest.object_id, chest.x, chest.y);
                    (sprite_x, sprite_y)  // Fallback to before sprite
                }
            } else {
                (sprite_x, sprite_y)  // Fallback to before sprite if object not found
            };
            
            let sprite_sheet = chest_obj.and_then(|o| o.sprite_sheet.clone());
            
            ChestData {
                id: chest.id.clone(),
                object_id: chest.object_id.clone(),  // Chest object ID (contains interactable data)
                open_object_id: None,  // Deprecated - no longer used
                x: chest.x,
                y: chest.y,
                sprite_x,  // Before (closed) state sprite coordinates
                sprite_y,  // Before (closed) state sprite coordinates
                open_sprite_x,  // After (open) state sprite coordinates
                open_sprite_y,  // After (open) state sprite coordinates
                sprite_sheet,
                is_open: chest.is_open,  // Current state: false = before (closed), true = after (open)
            }
        })
        .collect();
    
    // Check if current player is on stairs
    let on_stairs = if let Some(pid) = player_id {
        game.stairs_position.map_or(false, |(sx, sy)| {
            game.entities.iter().any(|e| e.id == pid && e.x == sx && e.y == sy)
        })
    } else {
        false
    };
    
    // Build players list
    let players: Vec<PlayerData> = game.entities.iter()
        .filter(|e| e.controller == EntityController::Player)
        .map(|entity| {
            // Get display name from GameObject, or use entity ID
            let name = game.object_registry.get_object(&entity.object_id)
                .map(|obj| obj.name.clone())
                .unwrap_or_else(|| entity.id.clone());
            
            // Check if this player has acted this turn
            let has_acted = game.players_acted_this_turn.contains(&entity.id);
            
            PlayerData {
                id: entity.id.clone(),
                name,
                is_alive: entity.is_alive(),
                has_acted_this_turn: has_acted,
            }
        })
        .collect();
    
    // Determine if it's the current player's turn
    let is_my_turn = if let Some(pid) = player_id {
        game.turn_phase == crate::game_state::TurnPhase::PlayerPhase &&
        !game.players_acted_this_turn.contains(pid) &&
        game.entities.iter().any(|e| e.id == pid && e.controller == EntityController::Player && e.is_alive())
    } else {
        false
    };
    
    GameUpdate {
        map: game.dungeon.tiles.clone(),
        entities,
        consumables,
        chests,
        players,
        current_player_id: player_id.map(|s| s.to_string()),
        width: game.dungeon.width,
        height: game.dungeon.height,
        messages: Vec::new(),
        stairs_position: game.stairs_position,
        on_stairs,
        level_complete: false,
        all_players_dead: game.are_all_players_dead(),
        restart_confirmed: false,
        turn_phase: match game.turn_phase {
            crate::game_state::TurnPhase::PlayerPhase => "player".to_string(),
            crate::game_state::TurnPhase::AIPhase => "ai".to_string(),
        },
        current_turn: game.current_turn,
        is_my_turn,
    }
}

pub async fn index() -> Html<&'static str> {
    Html(include_str!("../client/index.html"))
}

pub async fn schema_endpoint() -> Json<schema::GameObjectSchema> {
    Json(schema::GameObjectSchema::generate())
}

pub async fn generate_map_endpoint(
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<GameUpdate> {
    // Load config and generate a fresh map
    let config = match crate::config::GameConfig::load("game_config.toml") {
        Ok(cfg) => cfg,
        Err(_) => {
            // If config doesn't exist, create default
            let default_config = create_default_config();
            let _ = default_config.save("game_config.toml");
            default_config
        }
    };

    let tile_registry = crate::tile_registry::TileRegistry::load_from_config(&config);
    let object_registry = crate::game_object::GameObjectRegistry::load_from_config(&config);
    
    // Get level config if level parameter is provided
    let level_config = if let Some(level_str) = params.get("level") {
        if let Ok(level_num) = level_str.parse::<u32>() {
            log_debug(&format!("[MAP API] Looking for level {} in {} levels", level_num, config.levels.len()));
            let found = config.levels.iter().find(|l| l.level_number == level_num);
            if let Some(level) = found {
                log_debug(&format!("[MAP API] Found level {}: min_rooms={}, max_rooms={}", 
                    level.level_number, level.min_rooms, level.max_rooms));
            } else {
                log_debug(&format!("[MAP API] Level {} not found! Available levels: {:?}", 
                    level_num, config.levels.iter().map(|l| l.level_number).collect::<Vec<_>>()));
            }
            found
        } else {
            log_debug(&format!("[MAP API] Invalid level number: {}", level_str));
            None
        }
    } else {
        log_debug("[MAP API] No level parameter provided, using defaults");
        None
    };
    
    let mut game_state = if let Some(level) = level_config {
        GameState::new_with_level(tile_registry, object_registry, Some(level))
    } else {
        log_debug("[MAP API] Using default map generation (8-12 rooms)");
        GameState::new_with_registry(tile_registry, object_registry)
    };
    
    // Add a preview player for the map editor
    let preview_player_id = "preview_player".to_string();
    game_state.add_player(preview_player_id.clone());
    
    let mut update = game_state_to_update(&game_state, Some(&preview_player_id));
    
    // Check if preview player is on stairs
    update.on_stairs = game_state.stairs_position.map_or(false, |(sx, sy)| {
        game_state.entities.iter().any(|e| e.id == preview_player_id && e.x == sx && e.y == sy)
    });
    
    Json(update)
}

pub async fn websocket_handler(
    ws: WebSocketUpgrade,
    axum::extract::State((state, tx)): axum::extract::State<(SharedState, Tx)>,
) -> Response {
    ws.on_upgrade(|socket| handle_socket(socket, state, tx))
}

async fn handle_socket(socket: WebSocket, state: SharedState, tx: Tx) {
    let (mut sender, mut receiver) = socket.split();
    let mut rx = tx.subscribe();
    
    // Generate unique player ID for this connection
    use std::sync::atomic::{AtomicU64, Ordering};
    static PLAYER_COUNTER: AtomicU64 = AtomicU64::new(0);
    let player_id = format!("player_{}", PLAYER_COUNTER.fetch_add(1, Ordering::Relaxed));
    
    // Add new player entity to game state
    {
        let mut game = state.lock().unwrap();
        eprintln!("[WS] Adding new player: {}", player_id);
        let player_count_before = game.entities.iter()
            .filter(|e| e.controller == crate::entity::EntityController::Player)
            .count();
        eprintln!("[WS] Players before add: {}", player_count_before);
        game.add_player(player_id.clone());
        let player_count_after = game.entities.iter()
            .filter(|e| e.controller == crate::entity::EntityController::Player)
            .count();
        eprintln!("[WS] Players after add: {}", player_count_after);
    }

    // Send initial game state
    let initial_state = {
        let game = state.lock().unwrap();
        let mut update = game_state_to_update(&game, Some(&player_id));
        update.all_players_dead = game.are_all_players_dead();
        serde_json::to_string(&update).unwrap()
    };
    let _ = sender.send(Message::Text(initial_state)).await;

    // Spawn task to send updates to client
    let player_id_for_send_cleanup = player_id.clone();
    let state_for_send_cleanup = state.clone();
    let mut send_task = tokio::spawn(async move {
        while let Ok(msg) = rx.recv().await {
            if sender.send(Message::Text(msg)).await.is_err() {
                break;
            }
        }
        // Clean up player when send task ends (connection closed)
        let mut game = state_for_send_cleanup.lock().unwrap();
        eprintln!("[WS] Removing player {} (send task ended)", player_id_for_send_cleanup);
        game.remove_player(&player_id_for_send_cleanup);
        let player_count = game.entities.iter()
            .filter(|e| e.controller == crate::entity::EntityController::Player)
            .count();
        eprintln!("[WS] Players remaining: {}", player_count);
    });

    // Spawn task to receive messages from client
    let player_id_clone = player_id.clone();
    let state_for_recv = state.clone();
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(Message::Text(text))) = receiver.next().await {
            if let Ok(cmd) = serde_json::from_str::<PlayerCommand>(&text) {
                let mut game = state_for_recv.lock().unwrap();
                let (combat_messages, level_complete, restart_confirmed) = game.handle_command(&cmd, &player_id_clone);
                
                // Create update with messages
                let mut update = game_state_to_update(&game, Some(&player_id_clone));
                update.messages = combat_messages;
                update.level_complete = level_complete;
                update.restart_confirmed = restart_confirmed;
                update.all_players_dead = game.are_all_players_dead();
                
                let update_str = serde_json::to_string(&update).unwrap();
                let _ = tx.send(update_str);
            }
        }
    });

    let state_for_final_cleanup = state.clone();
    let player_id_for_final_cleanup = player_id.clone();
    tokio::select! {
        _ = (&mut send_task) => {
            recv_task.abort();
            // Also cleanup here in case recv_task cleanup didn't run
            let mut game = state_for_final_cleanup.lock().unwrap();
            eprintln!("[WS] Removing player {} (send_task ended, final cleanup)", player_id_for_final_cleanup);
            game.remove_player(&player_id_for_final_cleanup);
        },
        _ = (&mut recv_task) => {
            send_task.abort();
            // Cleanup when recv_task ends
            let mut game = state_for_final_cleanup.lock().unwrap();
            eprintln!("[WS] Removing player {} (recv_task ended, final cleanup)", player_id_for_final_cleanup);
            game.remove_player(&player_id_for_final_cleanup);
            // Also cleanup here in case send_task cleanup didn't run
            let mut game = state_for_final_cleanup.lock().unwrap();
            game.remove_player(&player_id_for_final_cleanup);
        },
    };
}

pub fn create_default_config() -> crate::config::GameConfig {
    use crate::game_object::{GameObject, SpriteCoord};
    
    let mut objects = Vec::new();
    
    // Wall tiles (non-walkable)
    let mut wall_dirt_top = GameObject::new(
        "wall_dirt_top".to_string(),
        "Dirt Wall (Top)".to_string(),
        "tile".to_string(),
        false,
        0, 0,
    );
    wall_dirt_top.sprite_sheet = Some("tiles.png".to_string());
    objects.push(wall_dirt_top);
    
    let mut wall_dirt_side = GameObject::new(
        "wall_dirt_side".to_string(),
        "Dirt Wall (Side)".to_string(),
        "tile".to_string(),
        false,
        1, 0,
    );
    wall_dirt_side.sprite_sheet = Some("tiles.png".to_string());
    objects.push(wall_dirt_side);
    
    let mut wall_stone_top = GameObject::new(
        "wall_stone_top".to_string(),
        "Stone Wall (Top)".to_string(),
        "tile".to_string(),
        false,
        0, 1,
    );
    wall_stone_top.sprite_sheet = Some("tiles.png".to_string());
    objects.push(wall_stone_top);
    
    // Floor tiles (walkable) - with multiple sprite variations for randomization
    let mut floor_dark = GameObject::new(
        "floor_dark".to_string(),
        "Dark Floor".to_string(),
        "tile".to_string(),
        true,
        0, 6,
    )
    .with_sprites(vec![
        SpriteCoord { x: 0, y: 6 },  // 7.a - blank floor (dark grey)
    ]);
    floor_dark.sprite_sheet = Some("tiles.png".to_string());
    objects.push(floor_dark);
    
    let mut floor_stone = GameObject::new(
        "floor_stone".to_string(),
        "Stone Floor".to_string(),
        "tile".to_string(),
        true,
        1, 6,
    )
    .with_sprites(vec![
        SpriteCoord { x: 1, y: 6 },  // 7.b - floor stone 1
        SpriteCoord { x: 2, y: 6 },  // 7.c - floor stone 2
        SpriteCoord { x: 3, y: 6 },  // 7.d - floor stone 3
    ]);
    floor_stone.sprite_sheet = Some("tiles.png".to_string());
    objects.push(floor_stone);
    
    // Stairs (goal object - not a tile!)
    let mut stairs = GameObject::new(
        "stairs".to_string(),
        "Stairs Down".to_string(),
        "goal".to_string(),  // New type: "goal" instead of "tile"
        true,  // Walkable (players can step on it)
        0, 7,  // Default sprite - should be set via editor
    );
    stairs.sprite_sheet = Some("tiles.png".to_string());
    objects.push(stairs);
    
    // Character/Player
    let mut player = GameObject::new(
        "player".to_string(),
        "Player Character".to_string(),
        "character".to_string(),
        true,  // Characters can move
        0, 0,  // Default sprite - should be set via editor
    )
    .with_health(100);
    player.sprite_sheet = Some("rogues.png".to_string());
    player.attack = Some(10);
    objects.push(player);
    
    // Orc monster
    let mut orc = GameObject::new(
        "orc".to_string(),
        "Orc".to_string(),
        "character".to_string(),
        true,
        0, 0,  // Default sprite - should be set via editor
    )
    .with_health(50);
    orc.sprite_sheet = Some("rogues.png".to_string());
    orc.attack = Some(5);
    orc.monster = Some(true);
    objects.push(orc);
    
    // Stairs (goal)
    let mut stairs = GameObject::new(
        "stairs".to_string(),
        "Stairs Down".to_string(),
        "goal".to_string(),
        true,
        7, 16,  // Stairs sprite coordinates
    );
    stairs.sprite_sheet = Some("tiles.png".to_string());
    objects.push(stairs);
    
    // Health potion (consumable)
    let mut health_potion = GameObject::new(
        "health_potion".to_string(),
        "Health Potion".to_string(),
        "consumable".to_string(),
        true,
        0, 0,  // Default sprite - should be set via editor
    );
    health_potion.sprite_sheet = Some("tiles.png".to_string());
    health_potion.healing_power = Some(20);
    objects.push(health_potion);
    
    crate::config::GameConfig { 
        game_objects: objects,
        levels: Vec::new(),
    }
}

