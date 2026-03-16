# Next Live — AI-Powered Conference Journey

> **Gemini Live Agent Challenge** — Live Agents Category
> 5 ADK Agents | 2 A2A Connections | 7 Google Cloud Services | Real-Time Voice

**Live Demo:** [next-live-agent-338756532561.us-central1.run.app](https://next-live-agent-338756532561.us-central1.run.app)
**Keynote Only:** [next-live-agent-338756532561.us-central1.run.app/keynote](https://next-live-agent-338756532561.us-central1.run.app/keynote)

---

## What It Does

Next Live is a **3-stage interactive AI experience** for Google Cloud Next 2026. Users enter their email, receive an AI-generated invitation (Imagen 4.0), book flights and hotels through a voice-powered travel concierge (Maya), and then join a live AI keynote presenter (Alex) who delivers highlights from Next '25 — all through real-time voice conversation.

**The meta-story:** Alex is an AI agent built with ADK that explains the AI agent ecosystem announced at the very conference where ADK was launched. When Alex answers a question about ADK, Alex is using the tool it's describing.

### The 3-Stage Journey

| Stage | Experience | Technology |
|-------|-----------|------------|
| **1. Invitation** | User enters email → Imagen generates a premium invitation card → sent to inbox via Resend API | Imagen 4.0 Fast, Resend API, REST endpoint |
| **2. Travel Booking** | Voice conversation with Maya (travel concierge) → searches real flights & hotels via A2A agents → confirms booking → sends itinerary email | Gemini Live API, ADK, A2A Protocol, google_search grounding |
| **3. Keynote** | Live voice keynote with Alex → Imagen slides generated in real-time → RAG-grounded in 264 minutes of conference transcripts → fully interruptible Q&A | Gemini Live API, ADK, Firestore Vector Search, Imagen 4.0 |

---

## Architecture

```
Stage 1: INVITATION (REST API)
  Browser → POST /api/invitation → Imagen 4.0 generates card → Resend sends email
  → UI renders invitation + "Call Travel Concierge" button

Stage 2: TRAVEL BOOKING (Gemini Live API, BIDI voice)
  Browser ←→ WebSocket /ws/concierge/{session_id}
  → ConciergeAgent "Maya" (voice: Aoede, gemini-live-2.5-flash-native-audio)
    → A2A JSON-RPC → HotelAgent (gemini-2.5-flash + google_search grounding)
    → A2A JSON-RPC → FlightAgent (gemini-2.5-flash + google_search grounding)
    → confirm_booking() → itinerary card + confirmation email
  → "Confirm & Join Keynote" button

Stage 3: KEYNOTE (Gemini Live API, BIDI voice)
  Browser ←→ WebSocket /ws/keynote/{session_id}
  → KeynoteAgent "Alex" (voice: Kore, gemini-live-2.5-flash-native-audio)
    → search_next25_sessions() → Firestore vector search (98 docs, 768-dim COSINE)
    → generate_slide() → Imagen 4.0 Fast (16:9 keynote slides)
    → Python callbacks (topic tracking, bridge suggestions — zero LLM cost)
  → 6-section presentation arc + interruptible Q&A
```

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
│   🎙️ Mic (16kHz) → WebSocket → 🔊 Speaker (24kHz)               │
│   📧 Email Input → REST API → 🖼️ Invitation Card                │
│   💬 Live Transcript → Chat Bubbles                              │
│   🖼️ Imagen Slides → Slide Display                               │
│   ✈️ Itinerary Card → Flight + Hotel Details                     │
└───────────────┬──────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────┐
│               CLOUD RUN — next-live-agent                        │
│                                                                  │
│   FastAPI + uvicorn (main.py)                                    │
│   ├── POST /api/invitation → Imagen + Resend email              │
│   ├── WS /ws/concierge/{id} → Maya (Aoede voice)                │
│   │     ├── search_flights() ──→ A2A ──→ FlightAgent            │
│   │     ├── search_hotels()  ──→ A2A ──→ HotelAgent             │
│   │     └── confirm_booking() → itinerary + email               │
│   ├── WS /ws/keynote/{id} → Alex (Kore voice)                   │
│   │     ├── search_next25_sessions() → Firestore RAG            │
│   │     ├── generate_slide() → Imagen 4.0                       │
│   │     └── callbacks → topic tracking (zero LLM cost)          │
│   ├── POST /a2a/hotel/ → HotelAgent (google_search)             │
│   └── POST /a2a/flight/ → FlightAgent (google_search)           │
│                                                                  │
│   A2A Protocol: Concierge → Hotel/Flight via JSON-RPC 2.0       │
│   Session-scoped queues: slides + itineraries (no cross-leak)    │
└───────┬──────────┬──────────┬──────────┬─────────────────────────┘
        │          │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼──────────┐
   │Gemini  │ │Firestore│ │Vertex│ │Google Search │
   │Live API│ │Vector DB│ │AI    │ │Grounding     │
   │BIDI    │ │98 docs  │ │Embed │ │Real flights/ │
   │Native  │ │768-dim  │ │Imagen│ │hotels        │
   │Audio   │ │COSINE   │ │4.0   │ │              │
   └────────┘ └─────────┘ └──────┘ └──────────────┘
```

---

## Agents (5 total, 2 A2A connections)

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| **Alex** (root) | `gemini-live-2.5-flash-native-audio` | Keynote presenter — 12 rhetorical techniques, 6-section arc, interruptible Q&A | `search_next25_sessions`, `generate_slide` |
| **Maya** (concierge) | `gemini-live-2.5-flash-native-audio` | Travel concierge — warm persona, books flights + hotels via voice | `search_flights`, `search_hotels`, `confirm_booking` |
| **HotelAgent** | `gemini-2.5-flash` | A2A hotel search — finds real hotels near Las Vegas Convention Center | `google_search` (grounding) |
| **FlightAgent** | `gemini-2.5-flash` | A2A flight search — finds real flights from user's city to LAS | `google_search` (grounding) |
| **InvitationTool** | `imagen-4.0-fast-generate-001` | Generates premium invitation cards (not an LLM agent — direct API) | Imagen API |

### A2A Protocol Usage

The ConciergeAgent (Maya) communicates with HotelAgent and FlightAgent via the **Agent-to-Agent (A2A) protocol** — JSON-RPC 2.0 over HTTP. This demonstrates multi-agent orchestration where agents built with different capabilities collaborate in real-time:

```
Maya says "Let me search for flights from Chicago"
  → search_flights() sends A2A JSON-RPC to /a2a/flight/
  → FlightAgent uses google_search grounding to find real flight options
  → Results returned via A2A Task response
  → Maya presents options conversationally via voice
```

Each A2A agent exposes a standard agent card at `/.well-known/agent-card.json` for discovery.

---

## Google Cloud Services (7)

| Service | Purpose | How It's Used |
|---------|---------|---------------|
| **Gemini Live API** | Real-time bidirectional voice streaming | Native audio I/O for Alex and Maya — BIDI WebSocket, VAD, interruption handling |
| **Agent Development Kit (ADK)** | Agent framework | 5 LlmAgents, FunctionTools, A2A integration, callbacks, RunConfig |
| **Cloud Run** | Hosting | WebSocket server with session affinity, 3600s timeout, 2 CPU, 4GB RAM, no-cpu-throttling |
| **Firestore** | Vector knowledge base | 98 documents, 768-dim COSINE vector index on `session_chunks` collection |
| **Vertex AI Embeddings** | Query embedding | `text-embedding-005` — 768 dimensions, RETRIEVAL_QUERY task type |
| **Vertex AI Imagen** | Image generation | `imagen-4.0-fast-generate-001` — invitation cards + keynote slides (~2-5s) |
| **Cloud Build** | CI/CD | `cloudbuild.yaml` — automated container builds + deployment (IaC bonus) |
| **Secret Manager** | API key storage | Resend API key stored securely, accessed at runtime by Cloud Run service account |

---

## Judging Criteria Coverage

### Innovation & Multimodal User Experience (40%)

| Criterion | How We Score |
|-----------|-------------|
| **Breaks text-box paradigm** | Entire experience is voice-first. Users speak naturally to Maya and Alex. No typing required for the core journey. |
| **See, Hear, Speak seamlessly** | **Hear:** Gemini Live API processes real-time audio input with automatic VAD. **Speak:** Native audio output (not TTS) with distinct voices (Aoede for Maya, Kore for Alex). **See:** Imagen generates invitation cards and keynote slides in real-time. Itinerary cards render live. |
| **Distinct persona/voice** | Maya is a warm travel concierge (Aoede voice, 40-60 words/turn). Alex is a world-class keynote presenter (Kore voice, 50-70 words/turn, 12 rhetorical techniques). |
| **Handles interruptions naturally** | VAD with `prefix_padding_ms=0` and `start_of_speech_sensitivity=HIGH`. Audio buffer instant-clear on interruption. Alex gracefully pivots: "Great thought — let me land this point." |
| **Context-aware, not disjointed** | Python callbacks track topics across turns (zero LLM cost). Bridge suggestions connect related topics: "You've asked about ADK and A2A — want me to show how they work together?" |
| **3-stage journey** | Not just one agent — a complete narrative arc: invitation → travel planning → keynote. Each stage flows naturally into the next. |

### Technical Implementation & Agent Architecture (30%)

| Criterion | How We Score |
|-----------|-------------|
| **Effective use of ADK** | 5 ADK agents with FunctionTools, callbacks, A2A integration. `before_agent_callback` and `after_agent_callback` for zero-cost context tracking. |
| **A2A Protocol** | 2 A2A connections (Concierge → Hotel, Concierge → Flight) via JSON-RPC 2.0. Agent cards at `/.well-known/agent-card.json`. Demonstrates cross-agent collaboration. |
| **Robustly hosted on Google Cloud** | Cloud Run with session affinity, 3600s timeout, min-instances=1, no-cpu-throttling. Secret Manager for API keys. Cloud Build CI/CD. |
| **Sound agent logic** | Each agent has single responsibility. Concierge orchestrates, Hotel/Flight search, Alex presents. Session-scoped queues prevent cross-session data leaks. |
| **Avoids hallucinations** | Every factual claim from Alex is RAG-grounded in Firestore vector search against 264 minutes of real Next '25 transcripts. Agent instruction: "NEVER state facts not in search_results." |
| **google_search grounding** | Hotel and Flight agents use `google_search` grounding tool to find real, current options — not hardcoded data. Results adapt to user preferences. |

### Demo & Presentation (30%)

| Criterion | How We Score |
|-----------|-------------|
| **Clear problem and solution** | 700+ sessions at Next '25 — how do you absorb it all? Next Live gives you a personal AI keynote presenter + travel concierge. |
| **Architecture diagram** | Full system diagram showing all 5 agents, A2A connections, 7 GCP services, and data flow. |
| **Proof of Cloud deployment** | Live URL on Cloud Run. `deploy.sh` + `cloudbuild.yaml` in repo. |
| **Actual software working** | Live interactive demo — speak to Maya, book travel, hear Alex present with Imagen slides. |

### Bonus Points

| Bonus | Status | Evidence |
|-------|--------|----------|
| **Automated deployment (IaC)** | +0.2 | `deploy.sh` + `cloudbuild.yaml` in repo |
| **Content publication** | TBD | Blog post pending |
| **GDG membership** | TBD | Profile link pending |

---

## Knowledge Base

- **4 Priority YouTube videos:** Developer Keynote, Opening Keynote, Introducing ADK, Keynote Highlights
- **98 chunks** in Firestore (2-minute windows, 15-second overlap)
- **264 minutes** of Google Cloud Next '25 content indexed
- **768-dimensional** embeddings via `text-embedding-005`
- **COSINE** distance vector search

---

## Performance Optimizations

- **1 LLM call per turn** for keynote (down from 4 — removed AgentTool chains)
- **Context tracking via Python callbacks** — zero LLM overhead for topic detection and bridge suggestions
- **VAD tuning:** `prefix_padding_ms=0`, `start_of_speech_sensitivity=HIGH` for instant speech detection
- **Audio buffer instant-clear** on interruption (custom AudioWorklet)
- **Presentation in 50-70 word bursts** for natural interruptibility
- **Session-scoped queues** prevent cross-session data leaks for slides and itineraries
- **A2A tool caching** — repeated tool calls return cached results instantly (120s TTL)
- **Imagen Fast model** — slide generation in ~2-5 seconds, non-blocking (delivered via separate queue)

---

## Setup & Deployment

### Prerequisites

- Google Cloud account with billing enabled
- Python 3.13+
- `gcloud` CLI authenticated

### Local Development

```bash
# Clone the repo
git clone https://github.com/hmshimanyula1995/google-hackathon-2026.git
cd google-hackathon-2026

# Set up environment
cp .env.example .env
# Edit .env with your Google Cloud project ID

# Install dependencies
pip install -r requirements.txt

# Set up knowledge base (run locally — YouTube blocks datacenter IPs)
python3 -m pipeline.01_fetch_transcripts --priority P0
python3 -m pipeline.03_chunk_and_embed
python3 -m pipeline.04_ingest_firestore --clear

# Start the server
python3 main.py
# Open http://localhost:8000
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | `next-live-agent` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Yes | `us-central1` | GCP region |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `True` | Use Vertex AI backend |
| `RESEND_API_KEY` | No | (Secret Manager) | Resend API key for emails |
| `INVITATION_EMAIL` | No | `hudsonshimanyula@gmail.com` | Default invitation email |
| `PORT` | No | `8000` (local) / `8080` (Cloud Run) | Server port |

### Deploy to Cloud Run

```bash
# One-command deployment
./deploy.sh
```

This runs `gcloud run deploy` with optimized settings:
- 2 CPU, 4GB RAM
- Session affinity enabled
- 3600s timeout (WebSocket persistence)
- No CPU throttling
- Min instances: 1 (warm start)

### CI/CD

The `cloudbuild.yaml` enables automated builds via Cloud Build:

```bash
gcloud builds submit --config cloudbuild.yaml
```

---

## Project Structure

```
├── main.py                          # FastAPI server: REST + 2 WebSocket endpoints + A2A routes
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Cloud Run container (Python 3.13-slim)
├── deploy.sh                        # One-command Cloud Run deployment
├── cloudbuild.yaml                  # CI/CD pipeline
│
├── next25_agent/                    # Alex — keynote presenter
│   ├── agent.py                     # Root agent + callbacks + vision agent
│   └── tools/
│       ├── search_tool.py           # Firestore vector search (text-embedding-005)
│       ├── image_tool.py            # Imagen slide generation
│       ├── a2a_search_tool.py       # A2A protocol wrapper for search
│       └── a2a_slide_tool.py        # A2A protocol wrapper for slides
│
├── concierge_agent/                 # Maya — travel concierge
│   └── agent.py                     # Concierge agent + confirm_booking + itinerary email
│
├── concierge_tools/                 # Tools for Maya
│   ├── hotel_tool.py                # A2A wrapper → HotelAgent
│   ├── flight_tool.py               # A2A wrapper → FlightAgent
│   └── invitation_tool.py           # Imagen invitation + Resend email
│
├── hotel_agent/                     # A2A hotel search agent
│   └── agent.py                     # LlmAgent with google_search grounding
│
├── flight_agent/                    # A2A flight search agent
│   └── agent.py                     # LlmAgent with google_search grounding
│
├── a2a_search_agent/                # Standalone A2A search service (architecture demo)
│   ├── agent.py                     # Search agent definition
│   └── server.py                    # A2A HTTP server
│
├── slide_agent/                     # Standalone slide operator (architecture demo)
│   ├── agent.py                     # Slide operator + create_slide tool
│   └── server.py                    # A2A HTTP server
│
├── static/                          # Custom frontend
│   ├── index.html                   # 3-stage journey: invitation → concierge → keynote
│   ├── keynote.html                 # Standalone keynote page (Alex only, /keynote)
│   ├── css/style.css                # Futuristic dark glassmorphic theme + animations
│   └── js/
│       ├── app.js                   # 3-stage WebSocket client + audio + stage machine
│       ├── keynote.js               # Standalone keynote client (independent audio)
│       ├── pcm-player-processor.js  # AudioWorklet: 24kHz playback
│       └── pcm-recorder-processor.js # AudioWorklet: 16kHz recording
│
└── pipeline/                        # Data ingestion (run locally)
    ├── 01_fetch_transcripts.py      # YouTube transcript download
    ├── 03_chunk_and_embed.py        # Chunk + embed via text-embedding-005
    ├── 04_ingest_firestore.py       # Batch write to Firestore
    └── sources.py                   # Video metadata
```

---

## Models Used

| Component | Model | Status | Purpose |
|-----------|-------|--------|---------|
| Alex (keynote) | `gemini-live-2.5-flash-native-audio` | GA | Real-time voice keynote with native audio |
| Maya (concierge) | `gemini-live-2.5-flash-native-audio` | GA | Real-time voice travel booking |
| Hotel/Flight agents | `gemini-2.5-flash` | GA | Text-only A2A agents with google_search grounding |
| Invitation + Slides | `imagen-4.0-fast-generate-001` | GA | Fast image generation (~2-5s) |
| Embeddings | `text-embedding-005` | GA | 768-dim document/query embeddings |

---

## Third-Party Integrations

| Service | Purpose | Authorization |
|---------|---------|---------------|
| **Resend** | Transactional email delivery (invitation + itinerary confirmation) | API key in Google Secret Manager |

---

## Team

- **Michael Hudson Shimanyula** — [github.com/hmshimanyula1995](https://github.com/hmshimanyula1995)

---

## License

This project was created for the Gemini Live Agent Challenge hackathon. All submissions remain the intellectual property of the entrants per contest rules (Section 12).
