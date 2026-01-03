use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    response::{Html, Response},
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
mod tile;
mod tile_registry;

use game::{GameState, PlayerCommand};

type SharedState = Arc<Mutex<GameState>>;
type Tx = broadcast::Sender<String>;

#[derive(Serialize, Deserialize, Debug, Clone)]
struct GameUpdate {
    map: Vec<Vec<crate::tile::Tile>>,
    player_x: usize,
    player_y: usize,
    player_sprite_x: u32,
    player_sprite_y: u32,
    player_sprite_sheet: Option<String>,  // Which sprite sheet the player uses
    width: usize,
    height: usize,
}

#[tokio::main]
async fn main() {
    // Load game configuration
    let config = match config::GameConfig::load("game_config.toml") {
        Ok(cfg) => {
            println!("Loaded game config from game_config.toml");
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
        .nest_service("/assets", ServeDir::new("assets"))
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
    println!("Server running on http://localhost:3000");
    axum::serve(listener, app).await.unwrap();
}

async fn index() -> Html<&'static str> {
    Html(include_str!("../client/index.html"))
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

    // Send initial game state
    let initial_state = {
        let game = state.lock().unwrap();
        // Get player sprite from GameObject
        let player_obj = game.object_registry.get_object(&game.player.object_id);
        let (player_sprite_x, player_sprite_y) = player_obj
            .and_then(|obj| obj.get_sprites_vec().first().map(|s| (s.x, s.y)))
            .unwrap_or((0, 0));
        let player_sprite_sheet = player_obj
            .and_then(|obj| obj.sprite_sheet.clone());
        
        serde_json::to_string(&GameUpdate {
            map: game.dungeon.tiles.clone(),
            player_x: game.player.x,
            player_y: game.player.y,
            player_sprite_x,
            player_sprite_y,
            player_sprite_sheet,
            width: game.dungeon.width,
            height: game.dungeon.height,
        })
        .unwrap()
    };
    let _ = sender.send(Message::Text(initial_state)).await;

    // Spawn task to send updates to client
    let mut send_task = tokio::spawn(async move {
        while let Ok(msg) = rx.recv().await {
            if sender.send(Message::Text(msg)).await.is_err() {
                break;
            }
        }
    });

    // Spawn task to receive messages from client
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(Message::Text(text))) = receiver.next().await {
            if let Ok(cmd) = serde_json::from_str::<PlayerCommand>(&text) {
                let mut game = state.lock().unwrap();
                game.handle_command(&cmd);
                
                // Broadcast update
                let player_obj = game.object_registry.get_object(&game.player.object_id);
                let (player_sprite_x, player_sprite_y) = player_obj
                    .and_then(|obj| obj.get_sprites_vec().first().map(|s| (s.x, s.y)))
                    .unwrap_or((0, 0));
                let player_sprite_sheet = player_obj
                    .and_then(|obj| obj.sprite_sheet.clone());
                
                let update = serde_json::to_string(&GameUpdate {
                    map: game.dungeon.tiles.clone(),
                    player_x: game.player.x,
                    player_y: game.player.y,
                    player_sprite_x,
                    player_sprite_y,
                    player_sprite_sheet,
                    width: game.dungeon.width,
                    height: game.dungeon.height,
                }).unwrap();
                let _ = tx.send(update);
            }
        }
    });

    tokio::select! {
        _ = (&mut send_task) => recv_task.abort(),
        _ = (&mut recv_task) => send_task.abort(),
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
    objects.push(player);
    
    config::GameConfig { game_objects: objects }
}

