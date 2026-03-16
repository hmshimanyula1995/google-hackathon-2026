/**
 * Next Live — 3-Stage Journey Client
 *
 * Stage 1: Landing → Invitation (REST)
 * Stage 2: Invitation → Concierge (WebSocket voice)
 * Stage 3: Concierge → Keynote (WebSocket voice)
 *
 * Based on google/adk-samples/bidi-demo pattern.
 */

let ws = null;
let audioPlayerNode = null;
let audioPlayerContext = null;
let audioRecorderNode = null;
let audioRecorderContext = null;
let mediaStream = null;
let isConnected = false;
let sessionId = null;
let activeAgent = null; // "concierge" | "keynote"
let currentStage = "landing"; // "landing" | "invitation" | "session"

// DOM elements
const landingPage = document.getElementById("landing-page");
const invitationPage = document.getElementById("invitation-page");
const sessionPage = document.getElementById("session-page");
const joinBtn = document.getElementById("join-btn");
const conciergeBtn = document.getElementById("concierge-btn");
const confirmKeynoteBtn = document.getElementById("confirm-keynote-btn");
const disconnectBtn = document.getElementById("disconnect-btn");
const sessionTitle = document.getElementById("session-title");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const chatMessages = document.getElementById("chat-messages");
const slideContainer = document.getElementById("slide-container");
const slideImage = document.getElementById("slide-image");
const slideTopic = document.getElementById("slide-topic");
const itineraryContainer = document.getElementById("itinerary-container");
const invitationLoading = document.getElementById("invitation-loading");
const invitationResult = document.getElementById("invitation-result");
const invitationImage = document.getElementById("invitation-image");
const invitationSent = document.getElementById("invitation-sent");
const audioVisualizer = document.getElementById("audio-visualizer");
const toolActivity = document.getElementById("tool-activity");
const toolActivityText = document.getElementById("tool-activity-text");

// --- Sound Effects (Web Audio API) ---
// Use a shared AudioContext initialized on first user gesture to avoid autoplay blocks

let _soundCtx = null;

function _getSoundCtx() {
    if (!_soundCtx || _soundCtx.state === "closed") {
        _soundCtx = new AudioContext();
    }
    if (_soundCtx.state === "suspended") {
        _soundCtx.resume();
    }
    return _soundCtx;
}

function playSound(type) {
    try {
        const ctx = _getSoundCtx();
        const now = ctx.currentTime;

        if (type === "connect") {
            const osc1 = ctx.createOscillator();
            const osc2 = ctx.createOscillator();
            const gain = ctx.createGain();
            osc1.type = "sine";
            osc1.frequency.setValueAtTime(523.25, now);
            osc2.type = "sine";
            osc2.frequency.setValueAtTime(659.25, now + 0.1);
            gain.gain.setValueAtTime(0.15, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            osc1.connect(gain);
            osc2.connect(gain);
            gain.connect(ctx.destination);
            osc1.start(now);
            osc1.stop(now + 0.15);
            osc2.start(now + 0.1);
            osc2.stop(now + 0.35);
        } else if (type === "notification") {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, now);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.5);
        } else if (type === "success") {
            const notes = [523.25, 659.25, 783.99];
            const gain = ctx.createGain();
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
            gain.connect(ctx.destination);
            notes.forEach((freq, i) => {
                const osc = ctx.createOscillator();
                osc.type = "sine";
                osc.frequency.setValueAtTime(freq, now + i * 0.1);
                osc.connect(gain);
                osc.start(now + i * 0.1);
                osc.stop(now + i * 0.1 + 0.15);
            });
        }
    } catch (e) {
        // Silently ignore
    }
}

// Init sound context on first user click (browser autoplay policy)
document.addEventListener("click", () => { _getSoundCtx(); }, { once: true });

// --- Stage Management (with page transitions) ---

const pages = [landingPage, invitationPage, sessionPage];
const pageMap = {
    landing: landingPage,
    invitation: invitationPage,
    session: sessionPage,
};

function setStage(stage) {
    const outgoing = pageMap[currentStage];
    const incoming = pageMap[stage];

    if (outgoing === incoming) return;

    // Exit outgoing
    if (outgoing && outgoing.style.display !== "none") {
        outgoing.classList.add("page-exit");
        setTimeout(() => {
            outgoing.style.display = "none";
            outgoing.classList.remove("page-exit");
        }, 350);
    } else {
        pages.forEach((p) => {
            if (p !== incoming) p.style.display = "none";
        });
    }

    // Enter incoming
    incoming.classList.add("page-enter");
    incoming.style.display = "flex";
    void incoming.offsetWidth;
    incoming.classList.remove("page-enter");
    incoming.classList.add("page-enter-active");

    setTimeout(() => {
        incoming.classList.remove("page-enter-active");
    }, 350);

    currentStage = stage;
}

// --- Audio Visualizer ---

function setSpeaking(isSpeaking) {
    if (isSpeaking) {
        audioVisualizer.classList.add("speaking");
    } else {
        audioVisualizer.classList.remove("speaking");
    }
}

// --- Tool Activity Indicator ---

const toolKeywords = [
    { pattern: /\b(search|searching|look up|looking up|pull up|pulling up|find|finding)\b.*\b(flight|flights)\b/i, text: "Searching for flights..." },
    { pattern: /\b(search|searching|look up|looking up|pull up|pulling up|find|finding)\b.*\b(hotel|hotels|accommodation)\b/i, text: "Finding hotels..." },
    { pattern: /\b(search|searching|look up|looking up|pull up|pulling up|find|finding)\b.*\b(session|sessions|talk|talks)\b/i, text: "Searching sessions..." },
    { pattern: /\b(let me|give me|one moment|just a moment|hang on)\b/i, text: "Searching..." },
];

function checkToolActivity(text) {
    for (const kw of toolKeywords) {
        if (kw.pattern.test(text)) {
            showToolActivity(kw.text);
            return;
        }
    }
}

function showToolActivity(text) {
    toolActivityText.textContent = text;
    toolActivity.style.display = "block";
}

function hideToolActivity() {
    toolActivity.style.display = "none";
}

// --- Typing Indicator ---

let typingIndicatorEl = null;

function showTypingIndicator() {
    if (typingIndicatorEl) return;

    typingIndicatorEl = document.createElement("div");
    typingIndicatorEl.className = "typing-indicator";

    const bubble = document.createElement("div");
    bubble.className = "typing-bubble";
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement("span");
        dot.className = "typing-dot";
        bubble.appendChild(dot);
    }
    typingIndicatorEl.appendChild(bubble);
    chatMessages.appendChild(typingIndicatorEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTypingIndicator() {
    if (typingIndicatorEl) {
        typingIndicatorEl.remove();
        typingIndicatorEl = null;
    }
}

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

// --- Chat Messages ---

let currentAlexBubble = null;
let currentUserBubble = null;

function addMessage(text, sender) {
    hideTypingIndicator();

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
    hideTypingIndicator();

    if (!currentAlexBubble) {
        currentAlexBubble = addMessage(text, "alex");
    } else {
        currentAlexBubble.textContent = text;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function updateUserTranscript(text) {
    if (!currentUserBubble) {
        currentUserBubble = addMessage(text, "user");
    } else {
        currentUserBubble.textContent = text;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function clearChat() {
    chatMessages.innerHTML = "";
    currentAlexBubble = null;
    currentUserBubble = null;
    hideTypingIndicator();
}

// --- WebSocket Connection (parameterized for concierge/keynote) ---

async function connect(agentType) {
    activeAgent = agentType;
    sessionId = crypto.randomUUID();

    const wsPath = agentType === "concierge"
        ? `/ws/concierge/${sessionId}`
        : `/ws/keynote/${sessionId}`;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${wsPath}`;

    const agentAvatar = document.getElementById("agent-avatar");
    
    // Update session page UI for this agent type
    sessionTitle.textContent = agentType === "concierge" ? "Travel Concierge" : "Keynote";
    disconnectBtn.textContent = agentType === "concierge" ? "End Call" : "End Session";
    
    if (agentType === "concierge") {
        agentAvatar.className = "agent-avatar maya-avatar";
        agentAvatar.innerHTML = `
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="17" fill="var(--google-yellow)" opacity="0.1" stroke="var(--google-yellow)" stroke-width="1"/>
                <circle cx="18" cy="18" r="12" fill="var(--google-yellow)" opacity="0.2"/>
                <path d="M18 10l2.5 5.5L26 18l-5.5 2.5L18 26l-2.5-5.5L10 18l5.5-2.5z" fill="var(--google-yellow)"/>
            </svg>
        `;
    } else {
        agentAvatar.className = "agent-avatar alex-avatar";
        agentAvatar.innerHTML = `
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="17" fill="var(--google-blue)" opacity="0.1" stroke="var(--google-blue)" stroke-width="1"/>
                <circle cx="18" cy="18" r="12" fill="var(--google-blue)" opacity="0.15"/>
                <path d="M18 11c-3.87 0-7 3.13-7 7s3.13 7 7 7 7-3.13 7-7-3.13-7-7-7zm0 2.5c1.24 0 2.25 1.01 2.25 2.25S19.24 18 18 18s-2.25-1.01-2.25-2.25S16.76 13.5 18 13.5zm0 9.5c-1.85 0-3.47-.93-4.44-2.35.02-1.47 2.96-2.28 4.44-2.28s4.42.81 4.44 2.28C21.47 22.07 19.85 23 18 23z" fill="var(--google-blue)"/>
            </svg>
        `;
    }
    
    slideContainer.style.display = "none";
    itineraryContainer.style.display = "none";
    itineraryContainer.classList.remove("revealed");
    hideToolActivity();
    setSpeaking(false);

    // Show image upload bar only for concierge
    const imageUploadBar = document.getElementById("image-upload-bar");
    if (imageUploadBar) {
        imageUploadBar.style.display = agentType === "concierge" ? "flex" : "none";
    }

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

    // Remove existing close handler to prevent race conditions during stage transition
    if (ws) {
        ws.onclose = null;
        ws.close();
    }

    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        isConnected = true;
        setStatus("connected");
        setStage("session");
        playSound("connect");

        if (agentType === "concierge") {
            addMessage("Connecting to Maya, your travel concierge...", "system");
            ws.send(JSON.stringify({
                text: "I just received my invitation to Google Cloud Next 2026. Help me plan my trip."
            }));
        } else {
            addMessage("Session live. Alex is starting the keynote...", "system");
            ws.send(JSON.stringify({ text: "Start the presentation" }));
        }
    };

    // Track speaking state for visualizer
    let lastAudioTime = 0;
    let speakingTimeout = null;

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Binary audio data — agent is speaking
            const int16Data = new Int16Array(event.data);
            if (audioPlayerNode) {
                audioPlayerNode.port.postMessage(int16Data);
            }
            
            // Remove thinking indicators
            if (toolActivityText.textContent === "Thinking...") {
                hideToolActivity();
            }
            const agentAvatar = document.getElementById("agent-avatar");
            if (agentAvatar) agentAvatar.classList.remove("thinking");
            
            // Show audio visualizer — reset timer on each audio chunk
            setSpeaking(true);
            lastAudioTime = Date.now();
            if (speakingTimeout) clearTimeout(speakingTimeout);
            speakingTimeout = setTimeout(() => {
                // If no audio for 500ms, stop visualizer
                if (Date.now() - lastAudioTime >= 450) {
                    setSpeaking(false);
                }
            }, 500);
        } else {
            const data = JSON.parse(event.data);

            if (data.type === "slide") {
                // Preload the image before displaying to avoid jank
                const img = new Image();
                img.onload = () => {
                    // Remove skeleton if present
                    const skeleton = slideContainer.querySelector(".slide-skeleton");
                    if (skeleton) skeleton.remove();

                    // Reset animation classes
                    slideImage.classList.remove("slide-enter");
                    slideTopic.classList.remove("slide-topic-enter");

                    slideImage.src = img.src;
                    slideImage.style.display = "block";
                    slideTopic.textContent = data.topic || "";
                    slideContainer.style.display = "block";

                    // Force reflow then re-trigger entrance animations
                    void slideImage.offsetWidth;
                    slideImage.classList.add("slide-enter");
                    slideTopic.classList.add("slide-topic-enter");

                    // Scroll chat after layout shift
                    requestAnimationFrame(() => {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    });
                };
                img.src = `data:image/png;base64,${data.image}`;
            } else if (data.type === "slide_loading") {
                // Show skeleton placeholder while Imagen generates
                slideImage.style.display = "none";
                slideImage.classList.remove("slide-enter");
                slideTopic.classList.remove("slide-topic-enter");
                slideTopic.textContent = data.topic || "Preparing slide...";
                slideTopic.classList.add("slide-topic-enter");

                if (!slideContainer.querySelector(".slide-skeleton")) {
                    const skeleton = document.createElement("div");
                    skeleton.className = "slide-skeleton";
                    slideContainer.insertBefore(skeleton, slideTopic);
                }
                slideContainer.style.display = "block";

                requestAnimationFrame(() => {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                });
            } else if (data.type === "slide_text") {
                // Text-only fallback (Imagen failed)
                const skeleton = slideContainer.querySelector(".slide-skeleton");
                if (skeleton) skeleton.remove();
                slideImage.style.display = "none";
                slideTopic.classList.remove("slide-topic-enter");
                slideTopic.textContent = data.topic || "";
                void slideTopic.offsetWidth;
                slideTopic.classList.add("slide-topic-enter");
                slideContainer.style.display = "block";

                requestAnimationFrame(() => {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                });
            } else if (data.type === "itinerary") {
                document.getElementById("itin-flight").textContent =
                    data.flight?.description || "Pending";
                document.getElementById("itin-hotel").textContent =
                    data.hotel?.description || "Pending";
                document.getElementById("itin-email").textContent =
                    data.traveler_email || "";
                itineraryContainer.style.display = "block";
                playSound("notification");
                setTimeout(() => {
                    itineraryContainer.classList.add("revealed");
                }, 600);
            } else if (data.type === "interrupted") {
                clearAudioBuffer();
                currentAlexBubble = null;
                setSpeaking(false);
                hideToolActivity();
            } else if (data.type === "transcript") {
                // Transcript streams word-by-word — show immediately
                hideTypingIndicator();
                updateAlexTranscript(data.text);

                if (toolActivityText.textContent === "Thinking...") {
                    hideToolActivity();
                }
                const agentAvatar = document.getElementById("agent-avatar");
                if (agentAvatar) agentAvatar.classList.remove("thinking");

                // Check if agent mentions searching — show indicator
                if (!toolActivity.style.display || toolActivity.style.display === "none") {
                    checkToolActivity(data.text);
                }
            } else if (data.type === "user_transcript") {
                updateUserTranscript(data.text);
                if (!toolActivity.style.display || toolActivity.style.display === "none") {
                    showToolActivity("Thinking...");
                }
                const agentAvatar = document.getElementById("agent-avatar");
                if (agentAvatar) agentAvatar.classList.add("thinking");
            } else if (data.type === "turn_complete") {
                currentAlexBubble = null;
                currentUserBubble = null;
                setSpeaking(false);
                hideToolActivity();
                const agentAvatar = document.getElementById("agent-avatar");
                if (agentAvatar) agentAvatar.classList.remove("thinking");
            } else if (data.type === "text") {
                hideTypingIndicator();
                addMessage(data.text, "alex");
                if (toolActivityText.textContent === "Thinking...") {
                    hideToolActivity();
                }
                const agentAvatar = document.getElementById("agent-avatar");
                if (agentAvatar) agentAvatar.classList.remove("thinking");
                checkToolActivity(data.text);
            }
        }
    };

    ws.onclose = () => {
        isConnected = false;
        setStatus("disconnected");
        stopAudio();
        setSpeaking(false);
        hideToolActivity();
        hideTypingIndicator();
    };

    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

function disconnect() {
    if (ws) {
        ws.onclose = null; // Prevent race conditions
        ws.close();
        ws = null;
    }
    stopAudio();
    isConnected = false;
    setStatus("disconnected");
    clearChat();
    setSpeaking(false);
    hideToolActivity();
    hideTypingIndicator();
    
    const agentAvatar = document.getElementById("agent-avatar");
    if (agentAvatar) agentAvatar.classList.remove("thinking");

    if (activeAgent === "concierge") {
        setStage("invitation");
    } else {
        setStage("landing");
    }
    activeAgent = null;
}

function setStatus(status) {
    statusDot.className = `status-dot ${status}`;
    const labels = { disconnected: "Disconnected", connecting: "Connecting...", connected: "Live" };
    statusText.textContent = labels[status] || status;
}

// --- Event Listeners ---

// Stage 1: Landing → Invitation
const emailInput = document.getElementById("email-input");

joinBtn.addEventListener("click", async () => {
    const email = emailInput.value.trim();
    if (!email || !email.includes("@")) {
        emailInput.style.borderColor = "#EA4335";
        emailInput.focus();
        emailInput.placeholder = "Please enter a valid email address";
        return;
    }
    emailInput.style.borderColor = "";

    setStage("invitation");
    invitationLoading.style.display = "block";
    invitationResult.style.display = "none";
    invitationResult.classList.remove("invitation-result-visible");

    try {
        const res = await fetch("/api/invitation", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
        });
        const data = await res.json();

        if (data.status === "success" && data.image) {
            invitationImage.src = `data:image/png;base64,${data.image}`;
            invitationImage.style.display = "block";
            if (data.email_sent) {
                invitationSent.textContent = `Invitation sent to ${data.email} — check your inbox!`;
            } else {
                invitationSent.textContent = `Your invitation for ${data.email} is ready!`;
            }
        } else {
            invitationImage.style.display = "none";
            invitationSent.textContent =
                "You're invited to Google Cloud Next 2026! April 22-24, Las Vegas Convention Center.";
        }

        invitationLoading.style.display = "none";
        invitationResult.style.display = "block";

        requestAnimationFrame(() => {
            invitationResult.classList.add("invitation-result-visible");
        });

        playSound("success");
    } catch (err) {
        console.error("Invitation failed:", err);
        invitationImage.style.display = "none";
        invitationSent.textContent =
            "You're invited to Google Cloud Next 2026! April 22-24, Las Vegas Convention Center.";
        invitationLoading.style.display = "none";
        invitationResult.style.display = "block";

        requestAnimationFrame(() => {
            invitationResult.classList.add("invitation-result-visible");
        });
    }
});

// Stage 2: Invitation → Concierge voice call
conciergeBtn.addEventListener("click", () => {
    connect("concierge");
});

// Stage 3: Concierge → Keynote
confirmKeynoteBtn.addEventListener("click", () => {
    // Navigate to standalone keynote page — completely fresh, no shared audio state
    if (ws) {
        ws.onclose = null;
        ws.close();
        ws = null;
    }
    stopAudio();
    window.location.href = "/keynote";
});

// Disconnect button
disconnectBtn.addEventListener("click", disconnect);

// --- Image Upload (Maya "See" capability) ---

const imageFileInput = document.getElementById("image-file-input");
const imageUploadBtn = document.getElementById("image-upload-btn");
const imagePreviewContainer = document.getElementById("image-preview-container");
const imagePreviewEl = document.getElementById("image-preview");
const imageSendBtn = document.getElementById("image-send-btn");
const imageCancelBtn = document.getElementById("image-cancel-btn");

let pendingImageBase64 = null;
let pendingImageMime = null;

if (imageUploadBtn) {
    imageUploadBtn.addEventListener("click", () => {
        imageFileInput.click();
    });
}

if (imageFileInput) {
    imageFileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result;
            imagePreviewEl.src = dataUrl;
            // Extract base64 and mime type
            const parts = dataUrl.split(",");
            pendingImageBase64 = parts[1];
            pendingImageMime = parts[0].match(/:(.*?);/)[1];
            // Show preview
            imagePreviewContainer.style.display = "flex";
            imageUploadBtn.style.display = "none";
        };
        reader.readAsDataURL(file);
    });
}

if (imageSendBtn) {
    imageSendBtn.addEventListener("click", () => {
        if (!pendingImageBase64 || !ws || ws.readyState !== WebSocket.OPEN) return;

        // Send image over WebSocket
        ws.send(JSON.stringify({
            image: pendingImageBase64,
            mime_type: pendingImageMime,
            text: "I am sharing a photo with you. What do you see? Can you help me with this?",
        }));

        // Show the image in chat as a user message
        const div = document.createElement("div");
        div.className = "message user";
        const img = document.createElement("img");
        img.src = imagePreviewEl.src;
        img.style.maxWidth = "200px";
        img.style.borderRadius = "12px";
        img.style.border = "1px solid var(--border)";
        div.appendChild(img);
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        addMessage("Shared a photo with Maya", "system");
        showToolActivity("Maya is looking at your photo...");

        // Reset
        pendingImageBase64 = null;
        pendingImageMime = null;
        imagePreviewContainer.style.display = "none";
        imageUploadBtn.style.display = "inline-flex";
        imageFileInput.value = "";
    });
}

if (imageCancelBtn) {
    imageCancelBtn.addEventListener("click", () => {
        pendingImageBase64 = null;
        pendingImageMime = null;
        imagePreviewContainer.style.display = "none";
        imageUploadBtn.style.display = "inline-flex";
        imageFileInput.value = "";
    });
}
