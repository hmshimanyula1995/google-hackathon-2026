/**
 * Next Live — Client-side BIDI streaming app
 * Based on google/adk-samples/bidi-demo pattern.
 * Handles audio in/out, instant interruption, transcription display.
 */

let ws = null;
let audioPlayerNode = null;
let audioPlayerContext = null;
let audioRecorderNode = null;
let audioRecorderContext = null;
let mediaStream = null;
let isConnected = false;
let sessionId = null;

// DOM elements
const connectBtn = document.getElementById("connect-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const chatMessages = document.getElementById("chat-messages");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");

// --- Audio Player (24kHz output from Gemini) ---

async function startAudioPlayer() {
    audioPlayerContext = new AudioContext({ sampleRate: 24000 });
    const workletUrl = new URL("./pcm-player-processor.js", import.meta.url);
    await audioPlayerContext.audioWorklet.addModule(workletUrl);
    audioPlayerNode = new AudioWorkletNode(audioPlayerContext, "pcm-player-processor");
    audioPlayerNode.connect(audioPlayerContext.destination);
    console.log("Audio player started (24kHz)");
}

function stopAudioPlayer() {
    if (audioPlayerNode) {
        audioPlayerNode.disconnect();
        audioPlayerNode = null;
    }
    if (audioPlayerContext) {
        audioPlayerContext.close();
        audioPlayerContext = null;
    }
}

function clearAudioBuffer() {
    if (audioPlayerNode) {
        audioPlayerNode.port.postMessage({ command: "endOfAudio" });
    }
}

// --- Audio Recorder (16kHz input to Gemini) ---

function convertFloat32ToPCM16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return int16Array.buffer;
}

async function startAudioRecorder() {
    mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
        },
    });

    audioRecorderContext = new AudioContext({ sampleRate: 16000 });
    const source = audioRecorderContext.createMediaStreamSource(mediaStream);
    const workletUrl = new URL("./pcm-recorder-processor.js", import.meta.url);
    await audioRecorderContext.audioWorklet.addModule(workletUrl);
    audioRecorderNode = new AudioWorkletNode(audioRecorderContext, "pcm-recorder-processor");

    audioRecorderNode.port.onmessage = (event) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            const pcmData = convertFloat32ToPCM16(event.data);
            ws.send(pcmData);
        }
    };

    source.connect(audioRecorderNode);
    audioRecorderNode.connect(audioRecorderContext.destination);
    console.log("Audio recorder started (16kHz)");
}

function stopAudioRecorder() {
    if (audioRecorderNode) {
        audioRecorderNode.disconnect();
        audioRecorderNode = null;
    }
    if (audioRecorderContext) {
        audioRecorderContext.close();
        audioRecorderContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
    }
}

// --- Chat Messages ---

function addMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return bubble;
}

let currentAlexBubble = null;

function updateAlexTranscript(text) {
    if (!currentAlexBubble) {
        currentAlexBubble = addMessage(text, "alex");
    } else {
        currentAlexBubble.textContent = text;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// --- WebSocket Connection ---

async function connect() {
    sessionId = crypto.randomUUID();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

    console.log("Connecting to:", wsUrl);
    setStatus("connecting");

    try {
        await startAudioPlayer();
        await startAudioRecorder();
    } catch (err) {
        console.error("Audio setup failed:", err);
        addMessage("Microphone access denied. Please allow microphone access and try again.", "system");
        setStatus("disconnected");
        return;
    }

    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        console.log("WebSocket connected");
        isConnected = true;
        setStatus("connected");
        addMessage("Connected! Say 'hey' to start the presentation.", "system");
    };

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Binary audio data — send to player
            const int16Data = new Int16Array(event.data);
            if (audioPlayerNode) {
                audioPlayerNode.port.postMessage(int16Data);
            }
        } else {
            // JSON event
            const data = JSON.parse(event.data);

            if (data.type === "interrupted") {
                // INSTANT buffer clear — this is the key fix
                clearAudioBuffer();
                console.log("Interrupted — audio buffer cleared");
                currentAlexBubble = null;
            } else if (data.type === "transcript") {
                updateAlexTranscript(data.text);
            } else if (data.type === "user_transcript") {
                addMessage(data.text, "user");
            } else if (data.type === "turn_complete") {
                currentAlexBubble = null;
            } else if (data.type === "text") {
                addMessage(data.text, "alex");
            }
        }
    };

    ws.onclose = () => {
        console.log("WebSocket closed");
        isConnected = false;
        setStatus("disconnected");
        stopAudioPlayer();
        stopAudioRecorder();
    };

    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        addMessage("Connection error. Try refreshing the page.", "system");
    };
}

function disconnect() {
    if (ws) {
        ws.close();
        ws = null;
    }
    stopAudioPlayer();
    stopAudioRecorder();
    isConnected = false;
    setStatus("disconnected");
}

function setStatus(status) {
    statusDot.className = `status-dot ${status}`;
    const labels = {
        disconnected: "Disconnected",
        connecting: "Connecting...",
        connected: "Live",
    };
    statusText.textContent = labels[status] || status;
    connectBtn.textContent = status === "connected" ? "Disconnect" : "Connect";
}

// --- Text Input ---

function sendText() {
    const text = textInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ text: text }));
    addMessage(text, "user");
    textInput.value = "";
}

// --- Event Listeners ---

connectBtn.addEventListener("click", () => {
    if (isConnected) {
        disconnect();
    } else {
        connect();
    }
});

sendBtn.addEventListener("click", sendText);

textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendText();
    }
});
