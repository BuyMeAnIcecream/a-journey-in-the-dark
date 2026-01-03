use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    response::{Html, Json, Response},
    routing::get,
    Router,
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;
use tower_http::services::ServeDir;

mod config;
mod dungeon;
mod game;
mod game_object;
mod game_object_registry;
mod schema;
mod tile;
mod tile_registry;

use game::{GameState, PlayerCommand, GameMessage};

type SharedState = Arc<Mutex<GameState>>;
type Tx = broadcast::Sender<String>;

#[derive(Serialize, Deserialize, Debug, Clone)]
struct EntityData {
    id: String,
    object_id: String,  // Reference to GameObject (e.g., "orc", "player")
    x: usize,
    y: usize,
    sprite_x: u32,
    sprite_y: u32,
    sprite_sheet: Option<String>,
    controller: crate::game::EntityController,
    current_health: u32,
    max_health: u32,
    attack: i32,
    defense: i32,
    facing_right: bool,  // true = facing right, false = facing left (needs mirroring)
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct ConsumableData {
    id: String,
    object_id: String,
    x: usize,
    y: usize,
    sprite_x: u32,
    sprite_y: u32,
    sprite_sheet: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct GameUpdate {
    map: Vec<Vec<crate::tile::Tile>>,
    entities: Vec<EntityData>,  // All entities (player + AI)
    consumables: Vec<ConsumableData>,  // All consumables on the map
    width: usize,
    height: usize,
    messages: Vec<GameMessage>,  // Game messages (combat, level events, system)
    stairs_position: Option<(usize, usize)>,  // Position of stairs (goal)
    on_stairs: bool,  // Whether the current player is on stairs
    level_complete: bool,  // Whether level is complete (all players confirmed)
    all_players_dead: bool,  // Whether all players are dead
    restart_confirmed: bool,  // Whether all players confirmed restart
}

#[tokio::main]
async fn main() {
    // Load game configuration
    let config = match config::GameConfig::load("game_config.toml") {
        Ok(cfg) => {
            cfg
        }
        Err(e) => {
            // Check if file exists - only create default if it doesn't exist
            let config_path = std::path::Path::new("game_config.toml");
            if !config_path.exists() {
                eprintln!("game_config.toml not found. Creating default config.");
                let default_config = create_default_config();
                let _ = default_config.save("game_config.toml");
                default_config
            } else {
                // File exists but has parse errors - don't overwrite it!
                eprintln!("ERROR: Could not parse game_config.toml: {}", e);
                eprintln!("The file exists but has errors. Please fix it manually or use the editor.");
                eprintln!("Server will exit to prevent data loss.");
                std::process::exit(1);
            }
        }
    };

    let tile_registry = tile_registry::TileRegistry::load_from_config(&config);
    let object_registry = game_object_registry::GameObjectRegistry::load_from_config(&config);
    let state = Arc::new(Mutex::new(GameState::new_with_registry(tile_registry, object_registry)));
    let (tx, _rx) = broadcast::channel(100);

    let app = Router::new()
        .route("/", get(index))
        .route("/ws", get(websocket_handler))
        .route("/api/map", get(generate_map_endpoint))
        .route("/api/schema", get(schema_endpoint))
        .nest_service("/assets", ServeDir::new("assets"))
        .nest_service("/client", ServeDir::new("client"))
        .with_state((state, tx));

    let listener = match tokio::net::TcpListener::bind("0.0.0.0:3000").await {
        Ok(listener) => listener,
        Err(e) if e.kind() == std::io::ErrorKind::AddrInUse => {
            eprintln!("Error: Port 3000 is already in use.");
            eprintln!("Please stop the existing server or use a different port.");
            eprintln!("You can kill the process with: lsof -ti :3000 | xargs kill -9");
            std::process::exit(1);
        }
        Err(e) => {
            eprintln!("Failed to bind to port 3000: {}", e);
            std::process::exit(1);
        }
    };
    axum::serve(listener, app).await.unwrap();
}

async fn index() -> Html<&'static str> {
    Html(include_str!("../client/index.html"))
}

async fn schema_endpoint() -> Json<schema::GameObjectSchema> {
    Json(schema::GameObjectSchema::generate())
}

async fn generate_map_endpoint() -> Json<GameUpdate> {
    // Load config and generate a fresh map
    let config = match config::GameConfig::load("game_config.toml") {
        Ok(cfg) => cfg,
        Err(_) => {
            // If config doesn't exist, create default
            let default_config = create_default_config();
            let _ = default_config.save("game_config.toml");
            default_config
        }
    };

    let tile_registry = tile_registry::TileRegistry::load_from_config(&config);
    let object_registry = game_object_registry::GameObjectRegistry::load_from_config(&config);
    let mut game_state = GameState::new_with_registry(tile_registry, object_registry);
    
    // Add a preview player for the map editor
    let preview_player_id = "preview_player".to_string();
    game_state.add_player(preview_player_id.clone());
    
    // Convert entities to EntityData (monsters + preview player)
    let entities: Vec<EntityData> = game_state.entities.iter()
        .filter(|e| e.is_alive())
        .map(|entity| {
            let obj = game_state.object_registry.get_object(&entity.object_id);
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
                facing_right: entity.facing_right,
            }
        })
        .collect();
    
    // Convert consumables to ConsumableData
    let consumables: Vec<ConsumableData> = game_state.consumables.iter()
        .map(|consumable| {
            let obj = game_state.object_registry.get_object(&consumable.object_id);
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
    
    // Check if preview player is on stairs
    let on_stairs = game_state.stairs_position.map_or(false, |(sx, sy)| {
        game_state.entities.iter().any(|e| e.id == preview_player_id && e.x == sx && e.y == sy)
    });
    
    Json(GameUpdate {
        map: game_state.dungeon.tiles.clone(),
        entities,
        consumables,
        width: game_state.dungeon.width,
        height: game_state.dungeon.height,
        messages: Vec::new(),
        stairs_position: game_state.stairs_position,
        on_stairs,
        level_complete: false,
        all_players_dead: false,
        restart_confirmed: false,
    })
}

async fn websocket_handler(
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
        game.add_player(player_id.clone());
    }

    // Send initial game state
    let initial_state = {
        let game = state.lock().unwrap();
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
        
        // Check if current player is on stairs
        let on_stairs = game.stairs_position.map_or(false, |(sx, sy)| {
            game.entities.iter().any(|e| e.id == player_id && e.x == sx && e.y == sy)
        });
        let all_players_dead = game.are_all_players_dead();
        let update = GameUpdate {
            map: game.dungeon.tiles.clone(),
            entities,
            consumables,
            width: game.dungeon.width,
            height: game.dungeon.height,
            messages: Vec::new(),  // No messages on initial state
            stairs_position: game.stairs_position,
            on_stairs,
            level_complete: false,
            all_players_dead,
            restart_confirmed: false,
        };
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
        game.remove_player(&player_id_for_send_cleanup);
    });

    // Spawn task to receive messages from client
    let player_id_clone = player_id.clone();
    let state_for_recv = state.clone();
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(Message::Text(text))) = receiver.next().await {
            if let Ok(cmd) = serde_json::from_str::<PlayerCommand>(&text) {
                let mut game = state_for_recv.lock().unwrap();
                let (combat_messages, level_complete, restart_confirmed) = game.handle_command(&cmd, &player_id_clone);
                
                // Broadcast update
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
                
                let messages = combat_messages;
                let all_players_dead = game.are_all_players_dead();
                
                // Check if current player is on stairs
                let on_stairs = game.stairs_position.map_or(false, |(sx, sy)| {
                    game.entities.iter().any(|e| e.id == player_id_clone && e.x == sx && e.y == sy)
                });
                
                let update = serde_json::to_string(&GameUpdate {
                    map: game.dungeon.tiles.clone(),
                    entities,
                    consumables,
                    width: game.dungeon.width,
                    height: game.dungeon.height,
                    messages,
                    stairs_position: game.stairs_position,
                    on_stairs,
                    level_complete,
                    all_players_dead,
                    restart_confirmed,
                }).unwrap();
                let _ = tx.send(update);
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
            game.remove_player(&player_id_for_final_cleanup);
        },
        _ = (&mut recv_task) => {
            send_task.abort();
            // Also cleanup here in case send_task cleanup didn't run
            let mut game = state_for_final_cleanup.lock().unwrap();
            game.remove_player(&player_id_for_final_cleanup);
        },
    };
}

fn create_default_config() -> config::GameConfig {
    use game_object::{GameObject, SpriteCoord};
    
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
    
    config::GameConfig { game_objects: objects }
}

