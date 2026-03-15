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
const landingPage = document.getElementById("landing-page");
const sessionPage = document.getElementById("session-page");
const joinBtn = document.getElementById("join-btn");
const disconnectBtn = document.getElementById("disconnect-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const chatMessages = document.getElementById("chat-messages");

// --- Audio Player (24kHz output from Gemini) ---

async function startAudioPlayer() {
    audioPlayerContext = new AudioContext({ sampleRate: 24000 });
    const workletUrl = new URL("./pcm-player-processor.js", import.meta.url);
    await audioPlayerContext.audioWorklet.addModule(workletUrl);
    audioPlayerNode = new AudioWorkletNode(audioPlayerContext, "pcm-player-processor");
    audioPlayerNode.connect(audioPlayerContext.destination);
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
}

function stopAudio() {
    if (audioPlayerNode) { audioPlayerNode.disconnect(); audioPlayerNode = null; }
    if (audioPlayerContext) { audioPlayerContext.close(); audioPlayerContext = null; }
    if (audioRecorderNode) { audioRecorderNode.disconnect(); audioRecorderNode = null; }
    if (audioRecorderContext) { audioRecorderContext.close(); audioRecorderContext = null; }
    if (mediaStream) { mediaStream.getTracks().forEach((t) => t.stop()); mediaStream = null; }
}

// --- Chat Messages (deduplication fix) ---

let currentAlexBubble = null;
let currentUserBubble = null;

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

function updateAlexTranscript(text) {
    if (!currentAlexBubble) {
        currentAlexBubble = addMessage(text, "alex");
    } else {
        currentAlexBubble.textContent = text;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function updateUserTranscript(text) {
    // Update the same bubble instead of creating duplicates
    if (!currentUserBubble) {
        currentUserBubble = addMessage(text, "user");
    } else {
        currentUserBubble.textContent = text;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// --- WebSocket Connection ---

async function connect() {
    sessionId = crypto.randomUUID();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

    setStatus("connecting");

    try {
        await startAudioPlayer();
        await startAudioRecorder();
    } catch (err) {
        console.error("Audio setup failed:", err);
        addMessage("Microphone access denied. Please allow microphone and try again.", "system");
        setStatus("disconnected");
        return;
    }

    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        isConnected = true;
        setStatus("connected");

        // Show session page, hide landing
        landingPage.style.display = "none";
        sessionPage.style.display = "flex";

        addMessage("Session live. Alex is preparing the keynote...", "system");
    };

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Binary audio data — send to player
            const int16Data = new Int16Array(event.data);
            if (audioPlayerNode) {
                audioPlayerNode.port.postMessage(int16Data);
            }
        } else {
            const data = JSON.parse(event.data);

            if (data.type === "interrupted") {
                clearAudioBuffer();
                currentAlexBubble = null;
            } else if (data.type === "transcript") {
                updateAlexTranscript(data.text);
            } else if (data.type === "user_transcript") {
                updateUserTranscript(data.text);
            } else if (data.type === "turn_complete") {
                // Finalize both bubbles for next turn
                currentAlexBubble = null;
                currentUserBubble = null;
            } else if (data.type === "text") {
                addMessage(data.text, "alex");
            }
        }
    };

    ws.onclose = () => {
        isConnected = false;
        setStatus("disconnected");
        stopAudio();
    };

    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

function disconnect() {
    if (ws) { ws.close(); ws = null; }
    stopAudio();
    isConnected = false;
    setStatus("disconnected");

    // Show landing page again
    sessionPage.style.display = "none";
    landingPage.style.display = "flex";

    // Clear chat
    chatMessages.innerHTML = "";
    currentAlexBubble = null;
    currentUserBubble = null;
}

function setStatus(status) {
    statusDot.className = `status-dot ${status}`;
    const labels = { disconnected: "Disconnected", connecting: "Connecting...", connected: "Live" };
    statusText.textContent = labels[status] || status;
}

// --- Event Listeners ---

joinBtn.addEventListener("click", connect);
disconnectBtn.addEventListener("click", disconnect);
