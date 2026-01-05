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
let gameConfig = null;  // Game config for sprite lookups
let spriteLookup = new Map();  // object_id -> { sprite_x, sprite_y, sprite_sheet }
let webglLighting = null;  // WebGL lighting overlay

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

// Load game config for sprite lookups
async function loadGameConfig() {
    try {
        const response = await fetch('/api/config');
        gameConfig = await response.json();
        
        // Build sprite lookup map
        if (gameConfig.game_objects) {
            for (const obj of gameConfig.game_objects) {
                const sprites = obj.sprites || [];
                if (sprites.length > 0) {
                    // For interactable objects, store both states
                    if (obj.interactable) {
                        // Before state (sprites[0])
                        if (sprites[0]) {
                            spriteLookup.set(`${obj.id}_before`, {
                                sprite_x: sprites[0].x,
                                sprite_y: sprites[0].y,
                                sprite_sheet: obj.sprite_sheet || DEFAULT_SPRITE_SHEET
                            });
                        }
                        // After state (sprites[1])
                        if (sprites[1]) {
                            spriteLookup.set(`${obj.id}_after`, {
                                sprite_x: sprites[1].x,
                                sprite_y: sprites[1].y,
                                sprite_sheet: obj.sprite_sheet || DEFAULT_SPRITE_SHEET
                            });
                        }
                    }
                    // Default state (first sprite)
                    spriteLookup.set(obj.id, {
                        sprite_x: sprites[0].x,
                        sprite_y: sprites[0].y,
                        sprite_sheet: obj.sprite_sheet || DEFAULT_SPRITE_SHEET
                    });
                }
            }
        }
        
        console.log('[Client] Loaded game config, sprite lookup entries:', spriteLookup.size);
    } catch (error) {
        console.error('[Client] Failed to load game config:', error);
    }
}

// Get sprite info from lookup
function getSpriteInfo(objectId, isOpen = false) {
    if (!objectId) {
        console.warn('[CLIENT] getSpriteInfo called with undefined objectId');
        return { sprite_x: 0, sprite_y: 0, sprite_sheet: DEFAULT_SPRITE_SHEET };
    }
    
    // For interactable objects, use state-specific lookup
    if (isOpen !== undefined) {
        const key = isOpen ? `${objectId}_after` : `${objectId}_before`;
        if (spriteLookup.has(key)) {
            return spriteLookup.get(key);
        }
    }
    // Fallback to default
    const result = spriteLookup.get(objectId);
    if (result) {
        return result;
    }
    console.warn('[CLIENT] Sprite not found for objectId:', objectId, 'isOpen:', isOpen);
    return { sprite_x: 0, sprite_y: 0, sprite_sheet: DEFAULT_SPRITE_SHEET };
}

// Load default sprite sheet
async function loadDefaultSpriteSheet() {
    await loadGameConfig();
    return loadSpriteSheet(DEFAULT_SPRITE_SHEET)
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
    
    // Also resize lighting overlay canvas
    const lightingCanvas = document.getElementById('lightingOverlay');
    if (lightingCanvas) {
        lightingCanvas.width = canvas.width;
        lightingCanvas.height = canvas.height;
        if (webglLighting) {
            webglLighting.resize();
        }
    }
    
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
            
            // Get sprite info from tile_id (new format) or fallback to sprite_x/sprite_y (old format)
            let spriteInfo;
            if (tile.tile_id) {
                spriteInfo = getSpriteInfo(tile.tile_id);
            } else if (tile.sprite_x !== undefined && tile.sprite_y !== undefined) {
                // Fallback for old format
                spriteInfo = {
                    sprite_x: tile.sprite_x,
                    sprite_y: tile.sprite_y,
                    sprite_sheet: DEFAULT_SPRITE_SHEET
                };
            } else {
                spriteInfo = getSpriteInfo('wall_dirt_top');
            }
            const srcX = spriteInfo.sprite_x * SPRITE_SHEET_TILE_SIZE;
            const srcY = spriteInfo.sprite_y * SPRITE_SHEET_TILE_SIZE;
            
            // Check if sprite sheet is loaded
            const tileSpriteSheet = getSpriteSheet(spriteInfo.sprite_sheet);
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
                
                // Get sprite info from object_id (closed state)
                const spriteInfo = getSpriteInfo(chest.object_id, false);
                const chestSpriteSheet = getSpriteSheet(spriteInfo.sprite_sheet);
                
                if (chestSpriteSheet && chestSpriteSheet.complete) {
                    const srcX = spriteInfo.sprite_x * SPRITE_SHEET_TILE_SIZE;
                    const srcY = spriteInfo.sprite_y * SPRITE_SHEET_TILE_SIZE;
                    
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
                
                // Get sprite info from object_id (open state)
                const spriteInfo = getSpriteInfo(chest.object_id, true);
                const chestSpriteSheet = getSpriteSheet(spriteInfo.sprite_sheet);
                
                if (chestSpriteSheet && chestSpriteSheet.complete) {
                    const srcX = spriteInfo.sprite_x * SPRITE_SHEET_TILE_SIZE;
                    const srcY = spriteInfo.sprite_y * SPRITE_SHEET_TILE_SIZE;
                    
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
            // Get sprite info from object_id
            const spriteInfo = getSpriteInfo(entity.object_id);
            const entitySpriteSheet = getSpriteSheet(spriteInfo.sprite_sheet);
            
            if (entitySpriteSheet && entitySpriteSheet.complete) {
                const srcX = spriteInfo.sprite_x * SPRITE_SHEET_TILE_SIZE;
                const srcY = spriteInfo.sprite_y * SPRITE_SHEET_TILE_SIZE;
                
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
                // Get sprite info from object_id
                const spriteInfo = getSpriteInfo(consumable.object_id);
                const consumableSpriteSheet = getSpriteSheet(spriteInfo.sprite_sheet);
                
                if (consumableSpriteSheet && consumableSpriteSheet.complete) {
                    const srcX = spriteInfo.sprite_x * SPRITE_SHEET_TILE_SIZE;
                    const srcY = spriteInfo.sprite_y * SPRITE_SHEET_TILE_SIZE;
                    
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
    
    // Apply WebGL lighting overlay (after all Canvas 2D rendering)
    if (webglLighting && playerFound) {
        webglLighting.render(playerX, playerY, viewportMinX, viewportMinY, offsetX, offsetY, TILE_SIZE);
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
    try {
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
    
    // Load sprite sheets based on sprite lookup (from config)
    const spriteSheetPromises = [];
    const spriteSheetsToLoad = new Set();
    
    // Collect all sprite sheets needed
    if (gameState.entities) {
        for (const entity of gameState.entities) {
            const spriteInfo = getSpriteInfo(entity.object_id);
            spriteSheetsToLoad.add(spriteInfo.sprite_sheet);
        }
    }
    if (gameState.consumables) {
        for (const consumable of gameState.consumables) {
            const spriteInfo = getSpriteInfo(consumable.object_id);
            spriteSheetsToLoad.add(spriteInfo.sprite_sheet);
        }
    }
    if (gameState.chests) {
        for (const chest of gameState.chests) {
            const spriteInfo = getSpriteInfo(chest.object_id, chest.is_open);
            spriteSheetsToLoad.add(spriteInfo.sprite_sheet);
        }
    }
    if (gameState.map) {
        for (const row of gameState.map) {
            for (const tile of row) {
                if (tile && tile.tile_id) {
                    const spriteInfo = getSpriteInfo(tile.tile_id);
                    spriteSheetsToLoad.add(spriteInfo.sprite_sheet);
                }
            }
        }
    }
    
    // Load all needed sprite sheets
    for (const sheetName of spriteSheetsToLoad) {
        spriteSheetPromises.push(
            loadSpriteSheet(sheetName)
                .catch((e) => console.error(`Could not load sprite sheet "${sheetName}":`, e))
        );
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
    console.log('[CLIENT] handleGameStateUpdate completed successfully');
    } catch (error) {
        console.error('[CLIENT] Error in handleGameStateUpdate:', error);
        console.error('[CLIENT] Error stack:', error.stack);
        throw error;
    }
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
        console.log('[CLIENT] WebSocket connection opened, readyState:', ws.readyState);
        if (statusDiv) {
            statusDiv.textContent = 'Connected - Waiting for game state...';
        }
        
        // Send a ping message to keep connection alive and verify bidirectional communication
        try {
            ws.send(JSON.stringify({ action: 'ping' }));
            console.log('[CLIENT] Sent ping message to server');
        } catch (error) {
            console.error('[CLIENT] Failed to send ping:', error);
        }
        
        // Send a ping to keep connection alive and verify it's working
        setTimeout(() => {
            if (ws.readyState === WebSocket.OPEN) {
                console.log('[CLIENT] WebSocket still open after 1 second, readyState:', ws.readyState);
                console.log('[CLIENT] Buffered amount:', ws.bufferedAmount);
            } else {
                console.warn('[CLIENT] WebSocket closed unexpectedly, readyState:', ws.readyState);
            }
        }, 1000);
        
        // Check again after 3 seconds to see if message arrived
        setTimeout(() => {
            if (ws.readyState === WebSocket.OPEN) {
                console.log('[CLIENT] WebSocket still open after 3 seconds');
                if (!gameState) {
                    console.warn('[CLIENT] Still no game state received after 3 seconds');
                    if (statusDiv) {
                        statusDiv.textContent = 'Connected but no game state received - Check server logs';
                    }
                }
            }
        }, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (statusDiv) {
            statusDiv.textContent = 'Connection error - Check console';
        }
    };
    
    ws.onmessage = async (event) => {
        console.log('[CLIENT] Received WebSocket message, length:', event.data.length);
        console.log('[CLIENT] Message type:', typeof event.data);
        console.log('[CLIENT] First 100 chars:', event.data.substring(0, 100));
        try {
            const newGameState = JSON.parse(event.data);
            console.log('[CLIENT] Parsed game state:', {
                hasMap: !!newGameState.map,
                mapSize: newGameState.map ? `${newGameState.width}x${newGameState.height}` : 'none',
                entities: newGameState.entities?.length || 0,
                players: newGameState.players?.length || 0,
                sampleTile: newGameState.map?.[0]?.[0]
            });
            console.log('[CLIENT] Calling handleGameStateUpdate...');
            await handleGameStateUpdate(newGameState);
            console.log('[CLIENT] handleGameStateUpdate completed');
            if (statusDiv) {
                statusDiv.textContent = 'Connected';
            }
        } catch (error) {
            console.error('[CLIENT] Error in onmessage:', error);
            console.error('[CLIENT] Error stack:', error.stack);
            console.error('[CLIENT] Raw data (first 500 chars):', event.data.substring(0, 500));
            if (statusDiv) {
                statusDiv.textContent = 'Error: ' + error.message;
            }
        }
    };
    
    ws.onclose = (event) => {
        console.log('[CLIENT] WebSocket closed:', event.code, event.reason, event.wasClean);
        if (statusDiv) {
            statusDiv.textContent = 'Disconnected. Reconnecting...';
        }
        setTimeout(connect, 1000);
    };
    
    ws.onerror = (error) => {
        console.error('[CLIENT] WebSocket error:', error);
        if (statusDiv) {
            statusDiv.textContent = 'WebSocket error - Check console';
        }
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
    
    // Initialize WebGL lighting overlay (on separate canvas)
    const lightingCanvas = document.getElementById('lightingOverlay');
    if (lightingCanvas) {
        // Match the main canvas size
        const mainCanvas = document.getElementById('gameContainer');
        if (mainCanvas) {
            lightingCanvas.width = mainCanvas.width;
            lightingCanvas.height = mainCanvas.height;
        }
        try {
            webglLighting = new WebGLLighting(lightingCanvas);
            console.log('[Client] WebGL lighting initialized');
        } catch (error) {
            console.warn('[Client] WebGL lighting not available:', error);
        }
    }
    
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

