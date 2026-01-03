# Multiplayer Testing Guide

## Running Multiple Server Instances

You can now run multiple server instances on different ports for testing multiplayer.

### Method 1: Command Line Argument

```bash
# Terminal 1 - Server on port 3000 (default)
cargo run

# Terminal 2 - Server on port 3001
cargo run 3001

# Terminal 3 - Server on port 3002
cargo run 3002
```

### Method 2: Using the Helper Script

```bash
# Terminal 1
./run_server.sh 3000

# Terminal 2
./run_server.sh 3001
```

### Method 3: Environment Variable

```bash
# Terminal 1
PORT=3000 cargo run

# Terminal 2
PORT=3001 cargo run
```

## Connecting Clients

Each server instance runs independently with its own game state:

- **Server 1 (port 3000)**: http://localhost:3000
- **Server 2 (port 3001)**: http://localhost:3001
- **Server 3 (port 3002)**: http://localhost:3002

Each client connects to a different server instance, so they will see different game worlds.

## Next Steps for True Multiplayer

To implement true multiplayer (multiple players in the same world), we would need to:
1. Have all clients connect to the same server instance
2. Assign unique entity IDs to each player
3. Broadcast all player movements to all connected clients
4. Handle player disconnection and reconnection

