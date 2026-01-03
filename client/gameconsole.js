// Game Console - Handles all message rendering and display

let consoleDiv = null;

// Initialize the console
function init() {
    consoleDiv = document.getElementById('console');
}

// Add a message to the console
function addMessage(message) {
    if (!consoleDiv) {
        consoleDiv = document.getElementById('console');
        if (!consoleDiv) {
            console.warn('Console div not found');
            return;
        }
    }
    
    const messageDiv = document.createElement('div');
    
    // Determine CSS class based on message type
    let className = '';
    switch (message.message_type) {
        case 'Combat':
            // Check if it's healing or damage
            if (message.damage > 0 && message.attacker && message.target && !message.target_died) {
                // Check if it's a healing message (healer name contains healing keywords)
                const isHealing = message.attacker.toLowerCase().includes('potion') || 
                                message.attacker.toLowerCase().includes('heal') ||
                                message.attacker.toLowerCase().includes('health');
                className = isHealing ? 'success' : 'combat';
            } else if (message.target_died) {
                className = 'death';
            } else {
                className = 'combat';
            }
            break;
        case 'LevelEvent':
            className = 'success';
            break;
        case 'System':
            className = 'combat';  // Default styling for system messages
            break;
        default:
            className = '';
    }
    
    messageDiv.className = `message ${className}`;
    
    // Use the pre-formatted text from server, or format it ourselves if needed
    if (message.text) {
        messageDiv.textContent = message.text;
    } else {
        // Fallback formatting (shouldn't happen if server generates messages correctly)
        if (message.message_type === 'Combat') {
            if (message.target_died) {
                messageDiv.textContent = `${message.attacker} killed ${message.target}!`;
            } else {
                const isHealing = message.attacker && (
                    message.attacker.toLowerCase().includes('potion') ||
                    message.attacker.toLowerCase().includes('heal') ||
                    message.attacker.toLowerCase().includes('health')
                );
                
                if (isHealing && message.target_health_after !== undefined) {
                    messageDiv.textContent = `${message.attacker} healed ${message.target} for ${message.damage} HP (${message.target_health_after} HP)`;
                } else if (message.target_health_after !== undefined) {
                    messageDiv.textContent = `${message.attacker} dealt ${message.damage} damage to ${message.target} (${message.target_health_after} HP)`;
                } else {
                    messageDiv.textContent = message.text || 'Combat occurred';
                }
            }
        } else {
            messageDiv.textContent = message.text || 'Event occurred';
        }
    }
    
    consoleDiv.appendChild(messageDiv);
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
    
    // Keep only last 50 messages
    while (consoleDiv.children.length > 50) {
        consoleDiv.removeChild(consoleDiv.firstChild);
    }
}

// Process an array of messages
function processMessages(messages) {
    if (!messages || !Array.isArray(messages)) {
        return;
    }
    
    messages.forEach(msg => {
        addMessage(msg);
    });
}

// Clear the console
function clear() {
    if (consoleDiv) {
        consoleDiv.innerHTML = '';
    }
}

// Export for browser use
if (typeof window !== 'undefined') {
    window.GameConsole = {
        init,
        addMessage,
        processMessages,
        clear
    };
}

