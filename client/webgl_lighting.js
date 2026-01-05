// WebGL Lighting Overlay
// Renders pulsing light effect on top of Canvas 2D rendering

class WebGLLighting {
    constructor(canvas) {
        this.canvas = canvas;
        this.gl = null;
        this.program = null;
        this.quadBuffer = null;
        
        // Lighting parameters
        this.lightRadius = 8;
        this.lightPulseSpeed = 0.003;
        this.minLightIntensity = 0.7;
        this.maxLightIntensity = 1.0;
        
        this.init();
    }
    
    init() {
        // Get WebGL context
        this.gl = this.canvas.getContext('webgl2') || 
                  this.canvas.getContext('webgl') || 
                  this.canvas.getContext('experimental-webgl');
        
        if (!this.gl) {
            console.warn('[WebGL Lighting] WebGL not supported, lighting disabled');
            return;
        }
        
        this.setupWebGL();
    }
    
    setupWebGL() {
        const gl = this.gl;
        
        // Create shader program
        this.program = this.createShaderProgram(
            this.getVertexShader(),
            this.getFragmentShader()
        );
        
        // Create fullscreen quad
        this.createQuad();
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
        // Use WebGL 1.0 for better compatibility
        return `
        attribute vec2 a_position;
        
        void main() {
            gl_Position = vec4(a_position, 0.0, 1.0);
        }`;
    }
    
    getFragmentShader() {
        // Use WebGL 1.0 for better compatibility
        return `
        precision mediump float;
        
        uniform vec2 u_resolution;
        uniform vec2 u_lightPos;
        uniform float u_lightRadius;
        uniform float u_lightIntensity;
        
        void main() {
            vec2 position = gl_FragCoord.xy;
            vec2 diff = position - u_lightPos;
            float distance = length(diff);
            float normalizedDist = distance / u_lightRadius;
            
            if (normalizedDist > 1.0) {
                gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);  // Completely dark
            } else {
                float falloff = 1.0 - (normalizedDist * normalizedDist);
                float brightness = u_lightIntensity * falloff;
                gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0 - brightness);
            }
        }`;
    }
    
    createQuad() {
        const gl = this.gl;
        
        // Fullscreen quad vertices (in clip space: -1 to 1)
        const vertices = new Float32Array([
            -1, -1,
             1, -1,
            -1,  1,
             1,  1,
        ]);
        
        this.quadBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
    }
    
    resize() {
        if (!this.gl) {
            return;  // WebGL not available
        }
        // Viewport will be set in render() method based on canvas dimensions
        // This method exists for API compatibility
    }
    
    render(playerX, playerY, viewportMinX, viewportMinY, offsetX, offsetY, tileSize) {
        if (!this.gl || !this.program) {
            return;  // WebGL not available
        }
        
        const gl = this.gl;
        const currentTime = Date.now();
        const pulsePhase = currentTime * this.lightPulseSpeed;
        const lightIntensity = this.minLightIntensity + 
            (this.maxLightIntensity - this.minLightIntensity) * 
            (Math.sin(pulsePhase) * 0.5 + 0.5);
        
        // Calculate player position in screen space
        const playerViewportX = playerX - viewportMinX;
        const playerViewportY = playerY - viewportMinY;
        const playerScreenX = playerViewportX * tileSize + offsetX + tileSize / 2;
        const playerScreenY = playerViewportY * tileSize + offsetY + tileSize / 2;
        
        // Set viewport
        gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        
        // Use lighting program
        gl.useProgram(this.program);
        
        // Set uniforms
        const resolutionLoc = gl.getUniformLocation(this.program, 'u_resolution');
        const lightPosLoc = gl.getUniformLocation(this.program, 'u_lightPos');
        const lightRadiusLoc = gl.getUniformLocation(this.program, 'u_lightRadius');
        const lightIntensityLoc = gl.getUniformLocation(this.program, 'u_lightIntensity');
        
        gl.uniform2f(resolutionLoc, this.canvas.width, this.canvas.height);
        gl.uniform2f(lightPosLoc, playerScreenX, playerScreenY);
        gl.uniform1f(lightRadiusLoc, this.lightRadius * tileSize);
        gl.uniform1f(lightIntensityLoc, lightIntensity);
        
        // Enable blending for darkening overlay
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        
        // Bind and draw quad
        const positionLoc = gl.getAttribLocation(this.program, 'a_position');
        gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
        gl.enableVertexAttribArray(positionLoc);
        gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);
        
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        
        gl.disableVertexAttribArray(positionLoc);
    }
}

