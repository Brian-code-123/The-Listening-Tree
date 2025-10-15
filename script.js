// 語音識別功能
class VoiceRecognition {
    constructor() {
        this.isListening = false;
        this.voiceButton = document.getElementById('voiceInput');
        this.textInput = document.getElementById('textInput');
        this.chatbox = document.getElementById('chatbox');
        
        this.initVoiceControls();
    }
    
    initVoiceControls() {
        this.voiceButton.addEventListener('click', () => {
            if (this.isListening) {
                this.stopVoiceRecognition();
            } else {
                this.startVoiceRecognition();
            }
        });
    }
    
    async startVoiceRecognition() {
        try {
            this.voiceButton.innerHTML = '🔴 錄音中...';
            this.voiceButton.style.backgroundColor = '#ff4444';
            this.isListening = true;
            
            const response = await fetch('/voice/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.status === 'error') {
                throw new Error(result.message);
            }
            
            // 顯示語音監聽狀態
            this.addSystemMessage('語音監聽已啟動，請開始說話...');
            
        } catch (error) {
            console.error('啟動語音識別失敗:', error);
            this.addSystemMessage('語音識別啟動失敗: ' + error.message);
            this.resetVoiceButton();
        }
    }
    
    async stopVoiceRecognition() {
        try {
            this.voiceButton.innerHTML = '⏹️ 停止中...';
            
            const response = await fetch('/voice/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.status === 'error') {
                throw new Error(result.message);
            }
            
            // 如果有識別結果，發送給聊天機器人
            if (result.transcript && result.transcript.trim()) {
                this.textInput.value = result.transcript;
                this.sendMessage();
                this.addSystemMessage(`語音識別: "${result.transcript}"`);
            } else {
                this.addSystemMessage('沒有檢測到語音內容');
            }
            
        } catch (error) {
            console.error('停止語音識別失敗:', error);
            this.addSystemMessage('語音識別錯誤: ' + error.message);
        } finally {
            this.resetVoiceButton();
        }
    }
    
    resetVoiceButton() {
        this.voiceButton.innerHTML = '🎤 語音輸入';
        this.voiceButton.style.backgroundColor = '';
        this.isListening = false;
    }
    
    addSystemMessage(text) {
        const systemMessage = document.createElement('div');
        systemMessage.className = 'system-message';
        systemMessage.innerHTML = `<span>${text}</span>`;
        this.chatbox.appendChild(systemMessage);
        this.chatbox.scrollTop = this.chatbox.scrollHeight;
    }
}

// 初始化語音識別
let voiceRecognition;

document.addEventListener('DOMContentLoaded', function() {
    voiceRecognition = new VoiceRecognition();
    
    // 現有的聊天功能...
    const button = document.getElementById("buttonInput");
    const input = document.getElementById("textInput");
    
    function sendMessage() {
        const userMessage = input.value;
        if (userMessage.trim() === "") return;
        
        // 添加用戶消息到聊天框
        addUserMessage(userMessage);
        input.value = "";
        
        // 獲取機器人回應
        getBotResponse(userMessage);
    }
    
    button.addEventListener("click", sendMessage);
    
    input.addEventListener("keypress", function(e) {
        if (e.key === "Enter") {
            sendMessage();
        }
    });
    
    function addUserMessage(message) {
        const userMessageDiv = document.createElement("div");
        userMessageDiv.className = "userText";
        userMessageDiv.innerHTML = `<span>${message}</span>`;
        document.getElementById("chatbox").appendChild(userMessageDiv);
        document.getElementById("chatbox").scrollTop = document.getElementById("chatbox").scrollHeight;
    }
    
    function getBotResponse(message) {
        fetch(`/get?msg=${encodeURIComponent(message)}`)
            .then(response => response.text())
            .then(response => {
                const botMessageDiv = document.createElement("div");
                botMessageDiv.className = "botText";
                botMessageDiv.innerHTML = `<span>${response}</span>`;
                document.getElementById("chatbox").appendChild(botMessageDiv);
                document.getElementById("chatbox").scrollTop = document.getElementById("chatbox").scrollHeight;
            })
            .catch(error => {
                console.error('Error:', error);
                const errorDiv = document.createElement("div");
                errorDiv.className = "botText";
                errorDiv.innerHTML = `<span>抱歉，發生錯誤，請稍後再試。</span>`;
                document.getElementById("chatbox").appendChild(errorDiv);
            });
    }
});