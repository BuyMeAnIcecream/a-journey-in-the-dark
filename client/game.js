// Game client JavaScript - separated from HTML for better organization

const TILE_SIZE = 32;
const SPRITE_SHEET_TILE_SIZE = 32;
const DEFAULT_SPRITE_SHEET = 'tiles.png';

let gameState = null;
let ws = null;
let spriteSheets = {};
let spriteSheetLoaded = false;
let statusDiv = null;
let myPlayerId = null;  // Store this client's own player ID

// Load a sprite sheet
function loadSpriteSheet(name) {
    return new Promise((resolve, reject) => {
        if (spriteSheets[name]) {
            resolve(spriteSheets[name]);
            return;
        }
        
        const img = new Image();
        img.onload = () => {
            spriteSheets[name] = img;
            resolve(img);
        };
        img.onerror = (e) => {
            console.error(`Failed to load sprite sheet "${name}":`, e);
            reject(e);
        };
        img.src = `/assets/${name}`;
    });
}

// Get sprite sheet by name, with fallback
function getSpriteSheet(name) {
    if (name && spriteSheets[name]) {
        return spriteSheets[name];
    }
    // Fallback to default
    return spriteSheets[DEFAULT_SPRITE_SHEET] || null;
}

// Load default sprite sheet
function loadDefaultSpriteSheet() {
    loadSpriteSheet(DEFAULT_SPRITE_SHEET)
        .then(() => {
            spriteSheetLoaded = true;
            render(); // Always render, even without gameState (shows placeholder)
        })
        .catch(() => {
            spriteSheetLoaded = true;  // Still allow rendering with fallback
            render(); // Always render, even without gameState (shows placeholder)
        });
}

// Render the game
function render() {
    const canvas = document.getElementById('gameContainer');
    if (!canvas) {
        console.error('Canvas element not found!');
        return;
    }
    
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) {
        console.error('Could not get 2D context from canvas!');
        return;
    }
    
    if (!gameState) {
        // Draw a simple test pattern even without gameState
        canvas.width = 320;
        canvas.height = 320;
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ff0000';
        ctx.fillRect(50, 50, 100, 100);
        ctx.fillStyle = '#ffffff';
        ctx.font = '20px Arial';
        ctx.fillText('No gameState', 50, 150);
        return;
    }
    
    // Find player position for camera (follow the current player this client controls)
    let playerX = 0;
    let playerY = 0;
    let playerFound = false;
    
    // Use our stored player ID, not the broadcast one
    const playerIdToFollow = myPlayerId || gameState.current_player_id;
    
    if (gameState.entities && playerIdToFollow) {
        // Find the current player entity (the one this client controls)
        const currentPlayer = gameState.entities.find(
            e => e.id === playerIdToFollow && 
                 e.controller === 'Player' && 
                 e.current_health > 0
        );
        
        if (currentPlayer) {
            playerX = currentPlayer.x;
            playerY = currentPlayer.y;
            playerFound = true;
        }
    }
    
    // Fallback: if current player not found, find any alive player
    if (!playerFound && gameState.entities) {
        for (const entity of gameState.entities) {
            if (entity.controller === 'Player' && entity.current_health > 0) {
                playerX = entity.x;
                playerY = entity.y;
                playerFound = true;
                break;
            }
        }
    }
    
    // If no player found, center on map origin
    if (!playerFound) {
        playerX = 0;
        playerY = 0;
    }
    
    // Camera viewport: 10x10 tiles centered on player
    const VIEWPORT_SIZE = 10;
    const HALF_VIEWPORT = Math.floor(VIEWPORT_SIZE / 2);
    
    // Calculate ideal viewport (before clamping)
    const idealViewportMinX = playerX - HALF_VIEWPORT;
    const idealViewportMinY = playerY - HALF_VIEWPORT;
    
    // Calculate viewport bounds (centered on player)
    let viewportMinX = playerX - HALF_VIEWPORT;
    let viewportMaxX = playerX + HALF_VIEWPORT;
    let viewportMinY = playerY - HALF_VIEWPORT;
    let viewportMaxY = playerY + HALF_VIEWPORT;
    
    // Clamp viewport to map boundaries
    viewportMinX = Math.max(0, viewportMinX);
    viewportMaxX = Math.min(gameState.width - 1, viewportMaxX);
    viewportMinY = Math.max(0, viewportMinY);
    viewportMaxY = Math.min(gameState.height - 1, viewportMaxY);
    
    // Calculate offset to center the viewport on canvas
    const offsetX = (viewportMinX - idealViewportMinX) * TILE_SIZE;
    const offsetY = (viewportMinY - idealViewportMinY) * TILE_SIZE;
    
    // Canvas size is always 10x10 tiles
    canvas.width = VIEWPORT_SIZE * TILE_SIZE;
    canvas.height = VIEWPORT_SIZE * TILE_SIZE;
    
    // Clear canvas with transparent background to ensure proper transparency
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Fill with black background for visibility
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw map tiles within viewport
    for (let y = viewportMinY; y <= viewportMaxY; y++) {
        for (let x = viewportMinX; x <= viewportMaxX; x++) {
            // Safety check for map bounds
            if (!gameState.map || !gameState.map[y] || gameState.map[y][x] === undefined) {
                // Draw fallback tile
                const viewportX = x - viewportMinX;
                const viewportY = y - viewportMinY;
                const destX = viewportX * TILE_SIZE + offsetX;
                const destY = viewportY * TILE_SIZE + offsetY;
                ctx.fillStyle = '#222222';
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                continue;
            }
            
            const tile = gameState.map[y][x];
            
            // Calculate position relative to viewport, with offset to center on canvas
            const viewportX = x - viewportMinX;
            const viewportY = y - viewportMinY;
            const destX = viewportX * TILE_SIZE + offsetX;
            const destY = viewportY * TILE_SIZE + offsetY;
            
            // Safety check for canvas bounds
            if (destX < 0 || destX >= canvas.width || destY < 0 || destY >= canvas.height) {
                continue;
            }
            
            if (!tile) {
                // Fallback: draw dark gray tile if tile is missing
                ctx.fillStyle = '#222222';
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                continue;
            }
            
            // Draw sprite from sprite sheet
            const srcX = (tile.sprite_x || 0) * SPRITE_SHEET_TILE_SIZE;
            const srcY = (tile.sprite_y || 0) * SPRITE_SHEET_TILE_SIZE;
            
            // Check if sprite sheet is loaded (tiles use default sprite sheet)
            const tileSpriteSheet = getSpriteSheet(DEFAULT_SPRITE_SHEET);
            if (tileSpriteSheet && tileSpriteSheet.complete) {
                // Ensure transparency is preserved for tiles
                ctx.globalCompositeOperation = 'source-over';
                ctx.imageSmoothingEnabled = false;
                ctx.drawImage(
                    tileSpriteSheet,
                    srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                    destX, destY, TILE_SIZE, TILE_SIZE
                );
            } else {
                // Fallback: draw colored rectangle based on walkable (more visible)
                ctx.fillStyle = tile.walkable ? '#555555' : '#222222';
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                // Add a border to make tiles more visible
                ctx.strokeStyle = tile.walkable ? '#777777' : '#444444';
                ctx.lineWidth = 1;
                ctx.strokeRect(destX, destY, TILE_SIZE, TILE_SIZE);
            }
        }
    }
    
    // Draw closed chests first (behind entities, so they block movement visually)
    if (gameState.chests && Array.isArray(gameState.chests)) {
        for (const chest of gameState.chests) {
            const isOpen = chest.is_open === true || chest.is_open === "true";
            if (isOpen) {
                continue; // Skip open chests - they'll be drawn separately
            }
            
            const chestX = chest.x;
            const chestY = chest.y;
            
            // Check if chest is within viewport
            if (chestX >= viewportMinX && chestX <= viewportMaxX &&
                chestY >= viewportMinY && chestY <= viewportMaxY) {
                
                // Calculate position relative to viewport, with offset to center on canvas
                const viewportX = chestX - viewportMinX;
                const viewportY = chestY - viewportMinY;
                const destX = viewportX * TILE_SIZE + offsetX;
                const destY = viewportY * TILE_SIZE + offsetY;
                
                // Get sprite sheet for this chest
                const chestSpriteSheet = getSpriteSheet(chest.sprite_sheet || DEFAULT_SPRITE_SHEET);
                
                // Use closed chest sprite coordinates
                const spriteX = chest.sprite_x;
                const spriteY = chest.sprite_y;
                
                // Debug: log to verify we're using the right coordinates
                console.log(`Closed chest at (${chestX}, ${chestY}): sprite=(${spriteX}, ${spriteY}), open_sprite=(${chest.open_sprite_x}, ${chest.open_sprite_y}), is_open=${chest.is_open}`);
                
                if (spriteX !== undefined && spriteY !== undefined && 
                    chestSpriteSheet && chestSpriteSheet.complete) {
                    const srcX = spriteX * SPRITE_SHEET_TILE_SIZE;
                    const srcY = spriteY * SPRITE_SHEET_TILE_SIZE;
                    
                    ctx.globalCompositeOperation = 'source-over';
                    ctx.imageSmoothingEnabled = false;
                    
                    ctx.drawImage(
                        chestSpriteSheet,
                        srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                        destX, destY, TILE_SIZE, TILE_SIZE
                    );
                } else {
                    // Fallback to colored rectangle if sprite not available
                    ctx.fillStyle = '#654321'; // Dark brown for closed chests
                    ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                }
            }
        }
    }
    
    // Draw open chests before entities (so they appear behind characters but are still visible)
    if (gameState.chests && Array.isArray(gameState.chests)) {
        for (const chest of gameState.chests) {
            const isOpen = chest.is_open === true || chest.is_open === "true";
            if (!isOpen) {
                continue; // Skip closed chests - they were already drawn
            }
            
            const chestX = chest.x;
            const chestY = chest.y;
            
            // Check if chest is within viewport
            if (chestX >= viewportMinX && chestX <= viewportMaxX &&
                chestY >= viewportMinY && chestY <= viewportMaxY) {
                
                // Calculate position relative to viewport, with offset to center on canvas
                const viewportX = chestX - viewportMinX;
                const viewportY = chestY - viewportMinY;
                const destX = viewportX * TILE_SIZE + offsetX;
                const destY = viewportY * TILE_SIZE + offsetY;
                
                // Get sprite sheet for this chest
                const chestSpriteSheet = getSpriteSheet(chest.sprite_sheet || DEFAULT_SPRITE_SHEET);
                
                // Use open chest sprite coordinates
                const spriteX = chest.open_sprite_x;
                const spriteY = chest.open_sprite_y;
                
                // Debug: log to verify we're using the right coordinates
                // console.log(`Open chest at (${chestX}, ${chestY}): sprite=(${chest.sprite_x}, ${chest.sprite_y}), open_sprite=(${spriteX}, ${spriteY}), is_open=${chest.is_open}`);
                
                if (spriteX !== undefined && spriteY !== undefined && 
                    chestSpriteSheet && chestSpriteSheet.complete) {
                    const srcX = spriteX * SPRITE_SHEET_TILE_SIZE;
                    const srcY = spriteY * SPRITE_SHEET_TILE_SIZE;
                    
                    ctx.globalCompositeOperation = 'source-over';
                    ctx.imageSmoothingEnabled = false;
                    
                    ctx.drawImage(
                        chestSpriteSheet,
                        srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                        destX, destY, TILE_SIZE, TILE_SIZE
                    );
                } else {
                    // Fallback to colored rectangle if sprite not available
                    ctx.fillStyle = '#8b4513'; // Light brown for open chests
                    ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                }
            }
        }
    }
    
    // Draw all entities (player + AI) on top of tiles, closed chests, and open chests, but behind consumables
    if (gameState.entities) {
        for (const entity of gameState.entities) {
            // Check if entity is within viewport
            if (entity.x < viewportMinX || entity.x > viewportMaxX ||
                entity.y < viewportMinY || entity.y > viewportMaxY) {
                continue; // Skip entities outside viewport
            }
            
            // Calculate position relative to viewport, with offset to center on canvas
            const viewportX = entity.x - viewportMinX;
            const viewportY = entity.y - viewportMinY;
            const destX = viewportX * TILE_SIZE + offsetX;
            const destY = viewportY * TILE_SIZE + offsetY;
            
            // Get sprite sheet for this entity
            const entitySpriteSheetName = entity.sprite_sheet || DEFAULT_SPRITE_SHEET;
            const entitySpriteSheet = getSpriteSheet(entitySpriteSheetName);
            
            if (entity.sprite_x !== undefined && entity.sprite_y !== undefined && 
                entitySpriteSheet && entitySpriteSheet.complete) {
                const srcX = entity.sprite_x * SPRITE_SHEET_TILE_SIZE;
                const srcY = entity.sprite_y * SPRITE_SHEET_TILE_SIZE;
                
                // Save canvas state
                ctx.save();
                
                // Ensure transparency is preserved
                ctx.globalCompositeOperation = 'source-over';
                ctx.imageSmoothingEnabled = false; // Pixel art should not be smoothed
                
                // Sprite naturally faces LEFT, so we flip when facing RIGHT
                if (entity.facing_right === true) {
                    // Facing right - flip horizontally (sprite naturally faces left, so flip to face right)
                    ctx.translate(destX + TILE_SIZE, destY);
                    ctx.scale(-1, 1);
                    ctx.drawImage(
                        entitySpriteSheet,
                        srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                        0, 0, TILE_SIZE, TILE_SIZE
                    );
                } else {
                    // Facing left - draw normally (sprite naturally faces left)
                    ctx.drawImage(
                        entitySpriteSheet,
                        srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                        destX, destY, TILE_SIZE, TILE_SIZE
                    );
                }
                
                // Restore canvas state
                ctx.restore();
                
                // Add a colored border to distinguish player from AI (after restore, so coordinates are normal)
                if (entity.controller === 'Player') {
                    ctx.strokeStyle = '#00ff00';
                    ctx.lineWidth = 2;
                    ctx.strokeRect(destX + 1, destY + 1, TILE_SIZE - 2, TILE_SIZE - 2);
                } else if (entity.controller === 'AI') {
                    ctx.strokeStyle = '#ff0000';
                    ctx.lineWidth = 2;
                    ctx.strokeRect(destX + 1, destY + 1, TILE_SIZE - 2, TILE_SIZE - 2);
                }
            } else {
                // Fallback to colored rectangle if sprite not available
                if (entity.controller === 'Player') {
                    ctx.fillStyle = '#00ff00';
                } else {
                    ctx.fillStyle = '#ff0000';
                }
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
            }
        }
    }
    
    // Draw consumables on top of everything (including chests)
    if (gameState.consumables && Array.isArray(gameState.consumables)) {
        for (const consumable of gameState.consumables) {
            const consumableX = consumable.x;
            const consumableY = consumable.y;
            
            // Check if consumable is within viewport
            if (consumableX >= viewportMinX && consumableX <= viewportMaxX &&
                consumableY >= viewportMinY && consumableY <= viewportMaxY) {
                
                // Calculate position relative to viewport, with offset to center on canvas
                const viewportX = consumableX - viewportMinX;
                const viewportY = consumableY - viewportMinY;
                const destX = viewportX * TILE_SIZE + offsetX;
                const destY = viewportY * TILE_SIZE + offsetY;
                
                // Get sprite sheet for this consumable
                const consumableSpriteSheet = getSpriteSheet(consumable.sprite_sheet || DEFAULT_SPRITE_SHEET);
                
                if (consumable.sprite_x !== undefined && consumable.sprite_y !== undefined && 
                    consumableSpriteSheet && consumableSpriteSheet.complete) {
                    const srcX = consumable.sprite_x * SPRITE_SHEET_TILE_SIZE;
                    const srcY = consumable.sprite_y * SPRITE_SHEET_TILE_SIZE;
                    
                    ctx.globalCompositeOperation = 'source-over';
                    ctx.imageSmoothingEnabled = false;
                    ctx.drawImage(
                        consumableSpriteSheet,
                        srcX, srcY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                        destX, destY, TILE_SIZE, TILE_SIZE
                    );
                } else {
                    // Fallback to colored rectangle if sprite not available
                    ctx.fillStyle = '#00ffff'; // Cyan for consumables
                    ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                }
            }
        }
    }
    
    // Draw stairs (goal object) on top of tiles and entities, but only if within viewport
    if (gameState.stairs_position && Array.isArray(gameState.stairs_position) && gameState.stairs_position.length === 2) {
        const stairsX = gameState.stairs_position[0];
        const stairsY = gameState.stairs_position[1];
        
        // Check if stairs are within viewport
        if (stairsX >= viewportMinX && stairsX <= viewportMaxX &&
            stairsY >= viewportMinY && stairsY <= viewportMaxY) {
            
            // Calculate position relative to viewport, with offset to center on canvas
            const viewportX = stairsX - viewportMinX;
            const viewportY = stairsY - viewportMinY;
            const destX = viewportX * TILE_SIZE + offsetX;
            const destY = viewportY * TILE_SIZE + offsetY;
            
            // Get stairs sprite from config (we'll need to load it from the stairs object)
            // For now, use a default sprite sheet and coordinates
            const stairsSpriteSheet = getSpriteSheet('tiles.png');
            if (stairsSpriteSheet && stairsSpriteSheet.complete) {
                // Stairs sprite coordinates from config (x=7, y=16)
                const stairsSpriteX = 7 * SPRITE_SHEET_TILE_SIZE;
                const stairsSpriteY = 16 * SPRITE_SHEET_TILE_SIZE;
                
                ctx.globalCompositeOperation = 'source-over';
                ctx.imageSmoothingEnabled = false;
                ctx.drawImage(
                    stairsSpriteSheet,
                    stairsSpriteX, stairsSpriteY, SPRITE_SHEET_TILE_SIZE, SPRITE_SHEET_TILE_SIZE,
                    destX, destY, TILE_SIZE, TILE_SIZE
                );
                
                // Also draw a bright border to make stairs more visible for debugging
                ctx.strokeStyle = '#00ffff';
                ctx.lineWidth = 3;
                ctx.strokeRect(destX, destY, TILE_SIZE, TILE_SIZE);
            } else {
                // Fallback: draw a bright yellow rectangle for stairs (very visible)
                ctx.fillStyle = '#ffff00';
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                ctx.strokeStyle = '#ff0000';
                ctx.lineWidth = 3;
                ctx.strokeRect(destX, destY, TILE_SIZE, TILE_SIZE);
                // Draw "S" text on it
                ctx.fillStyle = '#000000';
                ctx.font = 'bold 24px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('S', destX + TILE_SIZE / 2, destY + TILE_SIZE / 2);
            }
        }
    }
    
    // Draw death overlay if all players are dead
    if (gameState.all_players_dead) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#ff0000';
        ctx.font = 'bold 32px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('YOU DIED', canvas.width / 2, canvas.height / 2 - 20);
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '20px Arial';
        ctx.fillText('Waiting for all players to confirm restart...', canvas.width / 2, canvas.height / 2 + 20);
    }
}

// Update player list
function updatePlayerList() {
    const playerListDiv = document.getElementById('playerList');
    if (!playerListDiv || !gameState || !gameState.players) {
        return;
    }
    
    // Use our stored player ID, not the broadcast one
    const currentPlayerId = myPlayerId || gameState.current_player_id;
    
    if (gameState.players.length === 0) {
        playerListDiv.innerHTML = '<div style="color: #888;">No players</div>';
        return;
    }
    
    let html = '';
    for (const player of gameState.players) {
        const isCurrentPlayer = currentPlayerId && player.id === currentPlayerId;
        const color = isCurrentPlayer ? '#00ff00' : (player.is_alive ? '#fff' : '#888');
        const style = isCurrentPlayer ? 'font-weight: bold;' : '';
        const status = player.is_alive ? '●' : '✕';
        
        // Show turn status
        let turnStatus = '';
        if (player.is_alive) {
            if (player.has_acted_this_turn) {
                turnStatus = ' <span style="color: #888; font-size: 10px;">(acted)</span>';
            } else if (gameState.turn_phase === 'player') {
                turnStatus = ' <span style="color: #ffff00; font-size: 10px;">(turn)</span>';
            }
        }
        
        html += `<div style="color: ${color}; ${style}">${status} ${player.name}${turnStatus}</div>`;
    }
    
    playerListDiv.innerHTML = html;
}

// Update health bar
function updateHealthBar() {
    if (!gameState || !gameState.entities) {
        return;
    }
    
    // Find the current player entity (the one this client controls)
    // Use our stored player ID, not the broadcast one
    const playerIdToFind = myPlayerId || gameState.current_player_id;
    let player = null;
    if (playerIdToFind) {
        player = gameState.entities.find(
            e => e.id === playerIdToFind && 
                 e.controller === 'Player' && 
                 e.current_health > 0
        );
    }
    
    // Fallback: if current player not found, find any alive player
    if (!player) {
        player = gameState.entities.find(e => e.controller === 'Player' && e.current_health > 0);
    }
    
    if (!player) {
        // Player is dead or not found
        document.getElementById('healthText').textContent = '0 / 0';
        document.getElementById('healthFill').style.width = '0%';
        document.getElementById('healthFill').className = 'health-fill critical';
        document.getElementById('attackValue').textContent = '-';
        if (document.getElementById('defenseValue')) {
            document.getElementById('defenseValue').textContent = '-';
        }
        if (document.getElementById('critChanceValue')) {
            document.getElementById('critChanceValue').textContent = '-';
        }
        if (document.getElementById('critDamageValue')) {
            document.getElementById('critDamageValue').textContent = '-';
        }
        return;
    }
    
    // Update health text
    document.getElementById('healthText').textContent = `${player.current_health} / ${player.max_health}`;
    
    // Calculate health percentage
    const healthPercent = (player.current_health / player.max_health) * 100;
    document.getElementById('healthFill').style.width = `${healthPercent}%`;
    
    // Update health bar color based on percentage
    const healthFill = document.getElementById('healthFill');
    healthFill.className = 'health-fill';
    if (healthPercent > 75) {
        healthFill.classList.add('high');
    } else if (healthPercent > 50) {
        healthFill.classList.add('medium');
    } else if (healthPercent > 25) {
        healthFill.classList.add('low');
    } else {
        healthFill.classList.add('critical');
    }
    
    // Update attack value
    document.getElementById('attackValue').textContent = player.attack.toString();
    
    // Update defense value
    if (document.getElementById('defenseValue')) {
        document.getElementById('defenseValue').textContent = (player.defense || 0).toString();
    }
    
    // Update crit chance value
    if (document.getElementById('critChanceValue')) {
        document.getElementById('critChanceValue').textContent = (player.crit_chance_percent || 0).toString() + '%';
    }
    
    // Update crit damage value
    if (document.getElementById('critDamageValue')) {
        document.getElementById('critDamageValue').textContent = (player.crit_damage_percent || 100).toString() + '%';
    }
}

// Handle game state updates
async function handleGameStateUpdate(newGameState) {
    gameState = newGameState;
    
    // Store our player ID from the first update (if not already stored)
    if (!myPlayerId && gameState.current_player_id) {
        myPlayerId = gameState.current_player_id;
    }
    
    // Calculate is_my_turn based on our own player data (not the broadcast value)
    // This ensures each client gets the correct value
    const myPlayer = gameState.players && myPlayerId 
        ? gameState.players.find(p => p.id === myPlayerId)
        : null;
    
    const calculatedIsMyTurn = myPlayer && 
        gameState.turn_phase === 'player' && 
        !myPlayer.has_acted_this_turn && 
        myPlayer.is_alive;
    
    // Override the broadcast is_my_turn with our calculated value
    gameState.is_my_turn = calculatedIsMyTurn || false;
    
    // Update health bar
    updateHealthBar();
    
    // Update player list
    updatePlayerList();
    
    // Update status message with turn info
    if (statusDiv) {
        if (gameState.is_my_turn) {
            statusDiv.textContent = `Turn ${gameState.current_turn} - Your turn!`;
        } else if (gameState.turn_phase === 'ai') {
            statusDiv.textContent = `Turn ${gameState.current_turn} - AI phase...`;
        } else {
            statusDiv.textContent = `Turn ${gameState.current_turn} - Waiting for other players...`;
        }
    }
    
    // Stop movement if it's not the player's turn
    if (!gameState.is_my_turn) {
        stopMovementInterval();
        keysPressed.clear();
    }
    
    // Process all messages from server (combat, level events, system)
    if (gameState.messages && gameState.messages.length > 0) {
        if (window.GameConsole) {
            window.GameConsole.processMessages(gameState.messages);
        }
    }
    
    // Check if level is complete (reload page)
    if (gameState.level_complete) {
        setTimeout(() => {
            location.reload(); // Reload page for next level
        }, 2000);
        return;
    }
    
    // Check if restart was confirmed (level was restarted)
    if (gameState.restart_confirmed) {
        window.restartConfirmationShown = false;
        return;
    }
    
    // All players dead - level will auto-restart (no confirmation needed)
    
    // Check if player is on stairs and show confirmation dialog
    if (gameState.on_stairs && !window.stairsConfirmationShown) {
        window.stairsConfirmationShown = true;
        const confirmed = confirm('You found the stairs! Are you sure you are done here?');
        if (confirmed) {
            // Send confirmation to server
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: 'move_up', confirm_stairs: true }));
            }
        } else {
            window.stairsConfirmationShown = false;
        }
    } else if (!gameState.on_stairs) {
        window.stairsConfirmationShown = false;
    }
    
    // Ensure default sprite sheet is loaded first
    if (!spriteSheetLoaded) {
        try {
            await loadSpriteSheet(DEFAULT_SPRITE_SHEET);
            spriteSheetLoaded = true;
        } catch (e) {
            console.error('Failed to load default sprite sheet:', e);
            spriteSheetLoaded = true; // Still allow rendering with fallback
        }
    }
    
    // Load sprite sheets for all entities and consumables (wait for all to load)
    const spriteSheetPromises = [];
    if (gameState.entities) {
        for (const entity of gameState.entities) {
            if (entity.sprite_sheet) {
                spriteSheetPromises.push(
                    loadSpriteSheet(entity.sprite_sheet)
                        .catch((e) => console.error(`Could not load sprite sheet "${entity.sprite_sheet}":`, e))
                );
            }
        }
    }
    if (gameState.consumables) {
        for (const consumable of gameState.consumables) {
            if (consumable.sprite_sheet) {
                await loadSpriteSheet(consumable.sprite_sheet);
            }
        }
    }
    
    // Load sprite sheets for all chests
    if (gameState.chests) {
        for (const chest of gameState.chests) {
            if (chest.sprite_sheet) {
                spriteSheetPromises.push(
                    loadSpriteSheet(chest.sprite_sheet)
                        .catch((e) => console.error(`Could not load sprite sheet "${chest.sprite_sheet}":`, e))
                );
            }
        }
    }
    // Wait for all sprite sheets to load before rendering
    await Promise.all(spriteSheetPromises);
    
    // Update status message with turn info
    if (statusDiv) {
        if (gameState.is_my_turn) {
            statusDiv.textContent = `Turn ${gameState.current_turn} - Your turn!`;
        } else if (gameState.turn_phase === 'ai') {
            statusDiv.textContent = `Turn ${gameState.current_turn} - AI phase...`;
        } else {
            statusDiv.textContent = `Turn ${gameState.current_turn} - Waiting for other players...`;
        }
    }
    
    // Update health bar
    updateHealthBar();
    
    render();
}

// Initialize WebSocket connection
function connect() {
    if (!statusDiv) {
        statusDiv = document.getElementById('status');
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        if (statusDiv) {
            statusDiv.textContent = 'Connected - Waiting for game state...';
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (statusDiv) {
            statusDiv.textContent = 'Connection error - Check console';
        }
    };
    
    ws.onmessage = async (event) => {
        console.log('[CLIENT] Received WebSocket message, length:', event.data.length);
        try {
            const newGameState = JSON.parse(event.data);
            console.log('[CLIENT] Parsed game state:', {
                hasMap: !!newGameState.map,
                mapSize: newGameState.map ? `${newGameState.width}x${newGameState.height}` : 'none',
                entities: newGameState.entities?.length || 0,
                players: newGameState.players?.length || 0
            });
            await handleGameStateUpdate(newGameState);
        } catch (error) {
            console.error('Error parsing game state:', error);
            console.error('Raw data (first 500 chars):', event.data.substring(0, 500));
            if (statusDiv) {
                statusDiv.textContent = 'Error parsing game state - Check console';
            }
        }
    };
    
    ws.onclose = () => {
        if (statusDiv) {
            statusDiv.textContent = 'Disconnected. Reconnecting...';
        }
        setTimeout(connect, 1000);
    };
}

// Handle keyboard input with continuous movement
const keyMap = {
    'ArrowUp': 'move_up',
    'ArrowDown': 'move_down',
    'ArrowLeft': 'move_left',
    'ArrowRight': 'move_right',
    'w': 'move_up',
    's': 'move_down',
    'a': 'move_left',
    'd': 'move_right',
};

let keysPressed = new Set();
let movementInterval = null;
const MOVEMENT_DELAY = 150; // milliseconds between movements when holding a key

function sendMovementCommand() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (keysPressed.size === 0) return;
    
    // Check if it's the player's turn
    if (gameState && !gameState.is_my_turn) {
        // Not player's turn, don't send movement
        return;
    }
    
    // Get the first pressed key (prioritize arrow keys over WASD if both are pressed)
    let action = null;
    const arrowKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
    for (const key of arrowKeys) {
        if (keysPressed.has(key)) {
            action = keyMap[key];
            break;
        }
    }
    
    // If no arrow key, use WASD
    if (!action) {
        for (const key of keysPressed) {
            const mapped = keyMap[key] || keyMap[key.toLowerCase()];
            if (mapped) {
                action = mapped;
                break;
            }
        }
    }
    
    if (action) {
        ws.send(JSON.stringify({ action, confirm_stairs: null, confirm_restart: null }));
        // Stop movement interval after sending command - wait for server response
        // The interval will restart if it's still our turn
        stopMovementInterval();
        keysPressed.clear();
    }
}

function startMovementInterval() {
    if (movementInterval) return; // Already running
    
    // Check if it's still our turn before starting
    if (gameState && !gameState.is_my_turn) {
        return; // Not our turn, don't start
    }
    
    // Send first command immediately
    sendMovementCommand();
    
    // Then send commands at regular intervals (only if still our turn)
    movementInterval = setInterval(() => {
        // Check again before each command
        if (gameState && !gameState.is_my_turn) {
            stopMovementInterval();
            keysPressed.clear();
            return;
        }
        sendMovementCommand();
    }, MOVEMENT_DELAY);
}

function stopMovementInterval() {
    if (movementInterval) {
        clearInterval(movementInterval);
        movementInterval = null;
    }
}

function setupInputHandlers() {
    document.addEventListener('keydown', (e) => {
        // Ignore if key is already pressed
        if (keysPressed.has(e.key)) return;
        
        // Only handle movement keys
        if (!keyMap[e.key] && !keyMap[e.key.toLowerCase()]) return;
        
        // Check if it's the player's turn
        if (gameState && !gameState.is_my_turn) {
            // Not player's turn, ignore input
            return;
        }
        
        keysPressed.add(e.key);
        
        // Start continuous movement if this is the first key
        if (keysPressed.size === 1) {
            startMovementInterval();
        }
    });
    
    document.addEventListener('keyup', (e) => {
        keysPressed.delete(e.key);
        
        // Stop continuous movement if no keys are pressed
        if (keysPressed.size === 0) {
            stopMovementInterval();
        }
    });
}

// Initialize the game
function init() {
    statusDiv = document.getElementById('status');
    
    // Initialize console
    if (window.GameConsole) {
        window.GameConsole.init();
    }
    
    // Initial render to show placeholder
    render();
    
    // Load default sprite sheet and start connection
    loadDefaultSpriteSheet();
    setupInputHandlers();
    connect();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Export for use in HTML (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { render, loadDefaultSpriteSheet, loadSpriteSheet, getSpriteSheet, init, connect };
}

