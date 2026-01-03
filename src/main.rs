use axum::{
    routing::get,
    Router,
};
use tower_http::services::ServeDir;

mod api;
mod config;
mod dungeon;
mod game;
mod game_object;
mod tile;
mod tile_registry;

// New modules
mod message;
mod entity;
mod consumable;
mod chest;
mod combat;
mod ai;
mod map_generator;
mod game_state;

// SharedState and Tx are used via api module
use game_state::GameState;
use std::sync::Mutex;

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
                let default_config = api::create_default_config();
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
    let object_registry = game_object::GameObjectRegistry::load_from_config(&config);
    let state = std::sync::Arc::new(Mutex::new(GameState::new_with_registry(tile_registry, object_registry)));
    let (tx, _rx) = tokio::sync::broadcast::channel(100);

    let app = Router::new()
        .route("/", get(api::index))
        .route("/ws", get(api::websocket_handler))
        .route("/api/map", get(api::generate_map_endpoint))
        .route("/api/schema", get(api::schema_endpoint))
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
