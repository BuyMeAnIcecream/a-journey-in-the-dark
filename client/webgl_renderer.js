// WebGL Renderer for the game
// Handles sprite rendering, lighting, and all visual effects

const TILE_SIZE = 32;
const SPRITE_SHEET_TILE_SIZE = 32;

class WebGLRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.gl = null;
        this.spriteSheets = {};
        this.gameConfig = null;
        this.spriteLookup = new Map();  // object_id -> { sprite_x, sprite_y, sprite_sheet }
        
        // WebGL resources
        this.program = null;
        this.lightingProgram = null;
        this.vao = null;
        this.textures = new Map();  // sprite sheet name -> WebGL texture
        
        // Lighting parameters
        this.lightRadius = 8;
        this.lightPulseSpeed = 0.003;
        this.minLightIntensity = 0.7;
        this.maxLightIntensity = 1.0;
        
        this.init();
    }
    
    async init() {
        // Get WebGL context
        this.gl = this.canvas.getContext('webgl2');
        if (!this.gl) {
            // Fallback to WebGL 1.0
            this.gl = this.canvas.getContext('webgl') || this.canvas.getContext('experimental-webgl');
        }
        
        if (!this.gl) {
            throw new Error('WebGL not supported');
        }
        
        // Load game config
        await this.loadGameConfig();
        
        // Initialize WebGL
        this.setupWebGL();
    }
    
    async loadGameConfig() {
        try {
            const response = await fetch('/api/config');
            this.gameConfig = await response.json();
            
            // Build sprite lookup map
            if (this.gameConfig.game_objects) {
                for (const obj of this.gameConfig.game_objects) {
                    const sprites = obj.sprites || [];
                    if (sprites.length > 0) {
                        // For interactable objects, store both states
                        if (obj.interactable) {
                            // Before state (sprites[0])
                            if (sprites[0]) {
                                this.spriteLookup.set(`${obj.id}_before`, {
                                    sprite_x: sprites[0].x,
                                    sprite_y: sprites[0].y,
                                    sprite_sheet: obj.sprite_sheet || 'tiles.png'
                                });
                            }
                            // After state (sprites[1])
                            if (sprites[1]) {
                                this.spriteLookup.set(`${obj.id}_after`, {
                                    sprite_x: sprites[1].x,
                                    sprite_y: sprites[1].y,
                                    sprite_sheet: obj.sprite_sheet || 'tiles.png'
                                });
                            }
                        }
                        // Default state (first sprite)
                        this.spriteLookup.set(obj.id, {
                            sprite_x: sprites[0].x,
                            sprite_y: sprites[0].y,
                            sprite_sheet: obj.sprite_sheet || 'tiles.png'
                        });
                    }
                }
            }
            
            console.log('[WebGL] Loaded game config, sprite lookup entries:', this.spriteLookup.size);
        } catch (error) {
            console.error('[WebGL] Failed to load game config:', error);
            throw error;
        }
    }
    
    getSpriteInfo(objectId, isOpen = false) {
        // For interactable objects, use state-specific lookup
        const key = isOpen ? `${objectId}_after` : `${objectId}_before`;
        if (this.spriteLookup.has(key)) {
            return this.spriteLookup.get(key);
        }
        // Fallback to default
        return this.spriteLookup.get(objectId) || { sprite_x: 0, sprite_y: 0, sprite_sheet: 'tiles.png' };
    }
    
    setupWebGL() {
        const gl = this.gl;
        
        // Create shader program for sprite rendering
        this.program = this.createShaderProgram(
            this.getVertexShader(),
            this.getFragmentShader()
        );
        
        // Create shader program for lighting
        this.lightingProgram = this.createShaderProgram(
            this.getLightingVertexShader(),
            this.getLightingFragmentShader()
        );
        
        // Setup viewport
        this.resize();
    }
    
    resize() {
        // Canvas size is set by the main game code
        const gl = this.gl;
        gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    }
    
    createShaderProgram(vertexSource, fragmentSource) {
        const gl = this.gl;
        
        const vertexShader = this.compileShader(gl.VERTEX_SHADER, vertexSource);
        const fragmentShader = this.compileShader(gl.FRAGMENT_SHADER, fragmentSource);
        
        const program = gl.createProgram();
        gl.attachShader(program, vertexShader);
        gl.attachShader(program, fragmentShader);
        gl.linkProgram(program);
        
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            const error = gl.getProgramInfoLog(program);
            gl.deleteProgram(program);
            throw new Error('Shader program link error: ' + error);
        }
        
        return program;
    }
    
    compileShader(type, source) {
        const gl = this.gl;
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            const error = gl.getShaderInfoLog(shader);
            gl.deleteShader(shader);
            throw new Error('Shader compile error: ' + error);
        }
        
        return shader;
    }
    
    getVertexShader() {
        return `#version 300 es
        in vec2 a_position;
        in vec2 a_texCoord;
        
        uniform vec2 u_resolution;
        uniform vec2 u_camera;
        uniform float u_tileSize;
        
        out vec2 v_texCoord;
        
        void main() {
            vec2 position = (a_position - u_camera) * u_tileSize;
            vec2 clipSpace = ((position / u_resolution) * 2.0) - 1.0;
            gl_Position = vec4(clipSpace * vec2(1, -1), 0, 1);
            v_texCoord = a_texCoord;
        }`;
    }
    
    getFragmentShader() {
        return `#version 300 es
        precision mediump float;
        
        in vec2 v_texCoord;
        uniform sampler2D u_texture;
        
        out vec4 fragColor;
        
        void main() {
            fragColor = texture(u_texture, v_texCoord);
        }`;
    }
    
    getLightingVertexShader() {
        return `#version 300 es
        in vec2 a_position;
        
        uniform vec2 u_resolution;
        
        out vec2 v_position;
        
        void main() {
            vec2 clipSpace = ((a_position / u_resolution) * 2.0) - 1.0;
            gl_Position = vec4(clipSpace * vec2(1, -1), 0, 1);
            v_position = a_position;
        }`;
    }
    
    getLightingFragmentShader() {
        return `#version 300 es
        precision mediump float;
        
        in vec2 v_position;
        
        uniform vec2 u_lightPos;
        uniform float u_lightRadius;
        uniform float u_lightIntensity;
        uniform vec2 u_resolution;
        
        out vec4 fragColor;
        
        void main() {
            vec2 diff = v_position - u_lightPos;
            float distance = length(diff);
            float normalizedDist = distance / u_lightRadius;
            
            if (normalizedDist > 1.0) {
                fragColor = vec4(0.0, 0.0, 0.0, 1.0);  // Completely dark
            } else {
                float falloff = 1.0 - (normalizedDist * normalizedDist);
                float brightness = u_lightIntensity * falloff;
                fragColor = vec4(0.0, 0.0, 0.0, 1.0 - brightness);
            }
        }`;
    }
    
    async loadTexture(name) {
        if (this.textures.has(name)) {
            return this.textures.get(name);
        }
        
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                const gl = this.gl;
                const texture = gl.createTexture();
                gl.bindTexture(gl.TEXTURE_2D, texture);
                gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
                
                this.textures.set(name, texture);
                resolve(texture);
            };
            img.onerror = reject;
            img.src = `/assets/${name}`;
        });
    }
    
    render(gameState, playerX, playerY, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        const gl = this.gl;
        
        // Clear canvas
        gl.clearColor(0, 0, 0, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        
        // Enable blending for transparency
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        
        // Render tiles
        this.renderTiles(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Render closed chests
        this.renderChests(gameState, false, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Render entities
        this.renderEntities(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Render open chests
        this.renderChests(gameState, true, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Render consumables
        this.renderConsumables(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Render stairs
        this.renderStairs(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        
        // Apply lighting
        if (playerX !== undefined && playerY !== undefined) {
            this.renderLighting(playerX, playerY, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY);
        }
    }
    
    renderTiles(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        // TODO: Implement tile rendering
        // For now, this is a placeholder
    }
    
    renderChests(gameState, isOpen, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        // TODO: Implement chest rendering
    }
    
    renderEntities(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        // TODO: Implement entity rendering
    }
    
    renderConsumables(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        // TODO: Implement consumable rendering
    }
    
    renderStairs(gameState, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        // TODO: Implement stairs rendering
    }
    
    renderLighting(playerX, playerY, viewportMinX, viewportMinY, viewportMaxX, viewportMaxY, offsetX, offsetY) {
        const gl = this.gl;
        const currentTime = Date.now();
        const pulsePhase = currentTime * this.lightPulseSpeed;
        const lightIntensity = this.minLightIntensity + 
            (this.maxLightIntensity - this.minLightIntensity) * 
            (Math.sin(pulsePhase) * 0.5 + 0.5);
        
        // Calculate player position in screen space
        const playerViewportX = playerX - viewportMinX;
        const playerViewportY = playerY - viewportMinY;
        const playerScreenX = playerViewportX * TILE_SIZE + offsetX + TILE_SIZE / 2;
        const playerScreenY = playerViewportY * TILE_SIZE + offsetY + TILE_SIZE / 2;
        
        gl.useProgram(this.lightingProgram);
        
        // Set uniforms
        const resolutionLoc = gl.getUniformLocation(this.lightingProgram, 'u_resolution');
        const lightPosLoc = gl.getUniformLocation(this.lightingProgram, 'u_lightPos');
        const lightRadiusLoc = gl.getUniformLocation(this.lightingProgram, 'u_lightRadius');
        const lightIntensityLoc = gl.getUniformLocation(this.lightingProgram, 'u_lightIntensity');
        
        gl.uniform2f(resolutionLoc, this.canvas.width, this.canvas.height);
        gl.uniform2f(lightPosLoc, playerScreenX, playerScreenY);
        gl.uniform1f(lightRadiusLoc, this.lightRadius * TILE_SIZE);
        gl.uniform1f(lightIntensityLoc, lightIntensity);
        
        // Render fullscreen quad with lighting
        // TODO: Create and render fullscreen quad
    }
}

