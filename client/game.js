// Game client JavaScript - separated from HTML for better organization

const TILE_SIZE = 32;
const SPRITE_SHEET_TILE_SIZE = 32;
const DEFAULT_SPRITE_SHEET = 'tiles.png';

let gameState = null;
let ws = null;
let spriteSheets = {};
let spriteSheetLoaded = false;

// Load a sprite sheet
function loadSpriteSheet(name) {
    return new Promise((resolve, reject) => {
        if (spriteSheets[name]) {
            resolve(spriteSheets[name]);
            return;
        }
        
        const img = new Image();
        img.onload = () => {
            console.log(`Sprite sheet "${name}" loaded successfully:`, img.width, 'x', img.height);
            spriteSheets[name] = img;
            resolve(img);
        };
        img.onerror = (e) => {
            console.error(`Failed to load sprite sheet "${name}":`, e);
            console.log('Tried to load:', img.src);
            reject(e);
        };
        img.src = `/assets/${name}`;
        console.log(`Loading sprite sheet from:`, img.src);
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
            if (gameState) render();
        })
        .catch(() => {
            spriteSheetLoaded = true;  // Still allow rendering with fallback
            if (gameState) render();
        });
}

// Render the game
function render() {
    console.log('=== RENDER CALLED ===');
    console.log('gameState exists:', !!gameState);
    console.log('spriteSheetLoaded:', spriteSheetLoaded);
    
    const canvas = document.getElementById('gameContainer');
    const ctx = canvas.getContext('2d', { alpha: true });
    
    if (!gameState) {
        console.log('Render: No gameState - drawing test pattern');
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
    
    // Allow rendering even if sprite sheet isn't loaded (will use fallback)
    if (!spriteSheetLoaded) {
        console.log('Render: Sprite sheet not loaded yet, but rendering with fallback');
    }
    
    // Find player position for camera
    let playerX = 0;
    let playerY = 0;
    let playerFound = false;
    
    if (gameState.entities) {
        for (const entity of gameState.entities) {
            if (entity.controller === 'Player') {
                playerX = entity.x;
                playerY = entity.y;
                playerFound = true;
                console.log('Render: Found player at', playerX, playerY);
                break;
            }
        }
    }
    
    // If no player found, center on map origin
    if (!playerFound) {
        console.log('Render: No player found, using origin');
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
    
    console.log('Render: Viewport bounds:', {
        minX: viewportMinX,
        maxX: viewportMaxX,
        minY: viewportMinY,
        maxY: viewportMaxY,
        offsetX: offsetX,
        offsetY: offsetY,
        tilesToRender: (viewportMaxX - viewportMinX + 1) * (viewportMaxY - viewportMinY + 1)
    });
    
    // Canvas size is always 10x10 tiles
    canvas.width = VIEWPORT_SIZE * TILE_SIZE;
    canvas.height = VIEWPORT_SIZE * TILE_SIZE;
    
    console.log('Render: Canvas size set to', canvas.width, 'x', canvas.height);
    
    // Clear canvas with transparent background to ensure proper transparency
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Fill with black background for visibility
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw map tiles within viewport
    let tilesDrawn = 0;
    console.log('Render: Starting tile loop, map structure:', {
        mapExists: !!gameState.map,
        mapLength: gameState.map ? gameState.map.length : 0,
        firstRowLength: gameState.map && gameState.map[0] ? gameState.map[0].length : 0,
        viewportRange: `x: ${viewportMinX}-${viewportMaxX}, y: ${viewportMinY}-${viewportMaxY}`
    });
    
    for (let y = viewportMinY; y <= viewportMaxY; y++) {
        for (let x = viewportMinX; x <= viewportMaxX; x++) {
            // Safety check for map bounds
            if (!gameState.map || !gameState.map[y] || gameState.map[y][x] === undefined) {
                console.warn(`Render: Missing tile at map(${x}, ${y})`);
                // Draw fallback tile
                const viewportX = x - viewportMinX;
                const viewportY = y - viewportMinY;
                const destX = viewportX * TILE_SIZE + offsetX;
                const destY = viewportY * TILE_SIZE + offsetY;
                ctx.fillStyle = '#ff0000'; // Red for missing tiles (debug)
                ctx.fillRect(destX, destY, TILE_SIZE, TILE_SIZE);
                continue;
            }
            
            const tile = gameState.map[y][x];
            tilesDrawn++;
            
            // Calculate position relative to viewport, with offset to center on canvas
            const viewportX = x - viewportMinX;
            const viewportY = y - viewportMinY;
            const destX = viewportX * TILE_SIZE + offsetX;
            const destY = viewportY * TILE_SIZE + offsetY;
            
            // Safety check for canvas bounds
            if (destX < 0 || destX >= canvas.width || destY < 0 || destY >= canvas.height) {
                console.warn(`Render: Tile at (${x}, ${y}) would be drawn outside canvas at (${destX}, ${destY})`);
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
    
    // Draw all entities (player + AI) on top of tiles, but only if within viewport
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
    } else if (gameState.stairs_position) {
        console.log('WARNING: stairs_position is not in expected format:', gameState.stairs_position);
    }
    
    console.log('Render: Completed, drew', tilesDrawn, 'tiles');
}

// Export for use in HTML
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { render, loadDefaultSpriteSheet, loadSpriteSheet, getSpriteSheet };
}

