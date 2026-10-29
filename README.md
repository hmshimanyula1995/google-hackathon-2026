# Next Live — AI-Powered Conference Journey

A voice-first web app that takes a conference attendee through the whole trip: an AI-generated invitation, a voice travel concierge that finds flights and hotels, and a live AI keynote presenter that answers questions about the talks.

**Who it's for:** conference and event organizers who want an interactive, voice-driven attendee experience, and developers looking for a working reference of real-time voice agents (Gemini Live API + Google ADK + A2A) running on Cloud Run.

**Built with:** Python 3.13, FastAPI, Google ADK, Gemini Live API, A2A protocol, Imagen 4, Firestore vector search, Vertex AI, Cloud Run, and a vanilla JS + Web Audio (AudioWorklet) frontend.

**Status:** started as my solo entry to the Gemini Live Agent Challenge (March 2026). Next steps are in the [Roadmap](#roadmap).

> 5 ADK Agents | 2 A2A Connections | 8 Google Cloud Services | Real-Time Voice | See + Hear + Speak

**Live Demo:** [next-live-agent-338756532561.us-central1.run.app](https://next-live-agent-338756532561.us-central1.run.app)
**Keynote Direct:** [next-live-agent-338756532561.us-central1.run.app/keynote](https://next-live-agent-338756532561.us-central1.run.app/keynote)

---

## What It Does

Next Live reimagines Google Cloud Next as an **end-to-end AI agent experience**. From the moment you receive your invitation to the moment a keynote presenter takes the stage — every step is powered by AI agents that See, Hear, and Speak.

Users enter their email, receive an AI-generated invitation card (Imagen 4.0) delivered to their inbox, book flights and hotels through a voice-powered travel concierge who can also analyze photos you share, and then join a live AI keynote presenter who delivers highlights from Next '25 with real-time Imagen slides — all through natural voice conversation.

**The meta-story:** Alex is an AI agent built with ADK that explains the AI agent ecosystem announced at the very conference where ADK was launched. When Alex answers a question about ADK, Alex is using the tool it's describing.

### The 3-Stage Journey

| Stage | Experience | Technology |
|-------|-----------|------------|
| **1. Invitation** | Enter email → Imagen generates premium invitation card → delivered to inbox via Gmail SMTP | Imagen 4.0 Fast, Gmail SMTP, Secret Manager, REST endpoint |
| **2. Travel Booking** | Voice conversation with Maya → share hotel photos for visual analysis → search real flights & hotels via A2A agents → confirm booking → itinerary email sent | Gemini Live API, ADK, A2A Protocol, google_search grounding, image input |
| **3. Keynote** | Live voice keynote with Alex → Imagen slides generated in real-time → RAG-grounded in 264 minutes of conference transcripts → fully interruptible Q&A | Gemini Live API, ADK, Firestore Vector Search, Imagen 4.0 |

---

## Architecture

```
Stage 1: INVITATION (REST API)
  Browser → POST /api/invitation → Imagen 4.0 generates card → Gmail SMTP sends email
  → UI renders invitation + "Call Travel Concierge" button

Stage 2: TRAVEL BOOKING (Gemini Live API, BIDI voice + vision)
  Browser ←→ WebSocket /ws/concierge/{session_id}
  → ConciergeAgent "Maya" (voice: Aoede, gemini-live-2.5-flash-native-audio)
    → Accepts image uploads (hotel photos, flight screenshots) — SEE
    → A2A JSON-RPC → HotelAgent (gemini-2.5-flash + google_search grounding)
    → A2A JSON-RPC → FlightAgent (gemini-2.5-flash + google_search grounding)
    → confirm_booking() → itinerary card + Gmail confirmation email
  → "Confirm & Join Keynote" → navigates to /keynote

Stage 3: KEYNOTE (Gemini Live API, BIDI voice — standalone page)
  Browser ←→ WebSocket /ws/keynote/{session_id}
  → KeynoteAgent "Alex" (voice: Kore, gemini-live-2.5-flash-native-audio)
    → search_next25_sessions() → Firestore vector search (98 docs, 768-dim COSINE)
    → generate_slide() → Imagen 4.0 Fast (16:9 keynote slides)
    → Python callbacks (topic tracking, bridge suggestions — zero LLM cost)
  → 6-section presentation arc + interruptible Q&A
```

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                                  │
│   🎙️ Mic (16kHz PCM) ←→ WebSocket ←→ 🔊 Speaker (24kHz native audio) │
│   📧 Email Input → REST API → 🖼️ Imagen Invitation Card              │
│   📷 Image Upload → WebSocket → Maya analyzes visually (SEE)         │
│   💬 Live Transcript → Chat Bubbles                                   │
│   🖼️ Imagen Slides → Slide Display                                    │
│   ✈️ Itinerary Card → Flight + Hotel Details                          │
└────────────────┬─────────────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────────────┐
│                CLOUD RUN — next-live-agent                            │
│                                                                       │
│   FastAPI + uvicorn (main.py)                                         │
│   ├── GET /            → 3-stage journey (invitation → concierge)    │
│   ├── GET /keynote     → standalone keynote page (Alex only)         │
│   ├── POST /api/invitation → Imagen card + Gmail email               │
│   ├── WS /ws/concierge/{id} → Maya (Aoede voice, image input)       │
│   │     ├── search_flights() ──→ A2A JSON-RPC ──→ FlightAgent       │
│   │     ├── search_hotels()  ──→ A2A JSON-RPC ──→ HotelAgent        │
│   │     ├── confirm_booking() → itinerary card + Gmail email         │
│   │     └── image analysis → Maya describes hotel/flight photos      │
│   ├── WS /ws/keynote/{id} → Alex (Kore voice)                       │
│   │     ├── search_next25_sessions() → Firestore RAG                 │
│   │     ├── generate_slide() → Imagen 4.0 Fast                      │
│   │     └── before/after callbacks → topic tracking (0 LLM cost)     │
│   ├── POST /a2a/hotel/ → HotelAgent (google_search grounding)       │
│   └── POST /a2a/flight/ → FlightAgent (google_search grounding)     │
│                                                                       │
│   A2A Protocol: Concierge → Hotel/Flight via JSON-RPC 2.0            │
│   Session-scoped queues: slides + itineraries (no cross-leak)         │
│   Tool-level caching: prevents repeated A2A calls (120s TTL)          │
└───────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
        │          │          │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼────────┐ ┌▼───────────┐
   │Gemini  │ │Firestore│ │Vertex│ │Google      │ │Secret      │
   │Live API│ │Vector DB│ │AI    │ │Search      │ │Manager     │
   │BIDI    │ │98 docs  │ │Embed │ │Grounding   │ │Gmail pwd   │
   │Native  │ │768-dim  │ │Imagen│ │Real flights│ │            │
   │Audio   │ │COSINE   │ │4.0   │ │& hotels    │ │            │
   └────────┘ └─────────┘ └──────┘ └────────────┘ └────────────┘
```

---

## See, Hear, Speak — Full Multimodal Coverage

| Modality | Maya (Concierge) | Alex (Keynote) |
|----------|-----------------|----------------|
| **HEAR** | Real-time voice input via Gemini Live API | Real-time voice input via Gemini Live API |
| **SPEAK** | Native audio output, Aoede voice, 40-60 words/turn | Native audio output, Kore voice, 50-70 words/turn |
| **SEE (input)** | Image upload — analyzes hotel photos, flight screenshots | Vision agent (backend) for slide analysis |
| **SEE (output)** | Itinerary card, Imagen invitation card | Imagen keynote slides (16:9, real-time) |

---

## Agents (5 total, 2 A2A connections)

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| **Alex** (root) | `gemini-live-2.5-flash-native-audio` | Keynote presenter — 12 rhetorical techniques, 6-section arc, interruptible Q&A | `search_next25_sessions`, `generate_slide` |
| **Maya** (concierge) | `gemini-live-2.5-flash-native-audio` | Travel concierge — books flights + hotels via voice, analyzes shared images | `search_flights`, `search_hotels`, `confirm_booking` + image input |
| **HotelAgent** | `gemini-2.5-flash` | A2A hotel search — finds real hotels near Las Vegas Convention Center | `google_search` (grounding) |
| **FlightAgent** | `gemini-2.5-flash` | A2A flight search — finds real flights from user's city to LAS | `google_search` (grounding) |
| **InvitationTool** | `imagen-4.0-fast-generate-001` | Generates premium invitation cards + sends via Gmail | Imagen API + SMTP |

### A2A Protocol

Maya communicates with HotelAgent and FlightAgent via **A2A JSON-RPC 2.0 over HTTP**:

```
User says "I'm flying from Chicago"
  → Maya: "Let me pull up some flights for you!"
  → search_flights() sends A2A JSON-RPC to /a2a/flight/
  → FlightAgent uses google_search to find real flights
  → Results returned via A2A Task response
  → Maya presents options conversationally via voice
```

Agent cards available at `/a2a/hotel/.well-known/agent-card.json` and `/a2a/flight/.well-known/agent-card.json`.

---

## Google Cloud Services (8)

| Service | How It's Used |
|---------|---------------|
| **Gemini Live API** | BIDI voice streaming — native audio I/O for Alex and Maya, VAD, interruption handling |
| **Agent Development Kit (ADK)** | 5 LlmAgents, FunctionTools, A2A JSON-RPC, before/after callbacks, RunConfig |
| **Cloud Run** | FastAPI WebSocket server — session affinity, 3600s timeout, 2 CPU, 4GB RAM |
| **Firestore** | Vector knowledge base — 98 docs, 768-dim COSINE index on `session_chunks` |
| **Vertex AI Embeddings** | `text-embedding-005` — 768-dim query/document embeddings |
| **Vertex AI Imagen** | `imagen-4.0-fast-generate-001` — invitation cards + keynote slides (~2-5s) |
| **Cloud Build** | CI/CD — `cloudbuild.yaml` automated container builds + deployment |
| **Secret Manager** | Gmail app password stored securely, accessed by Cloud Run service account |

---

## Background

Next Live was built solo for Google's Gemini Live Agent Challenge (Devpost, Live Agents category, deadline March 16, 2026). The write-up is in [`blog-post.md`](blog-post.md); the contest judging-criteria mapping lives in the git history.

---

## Setup & Deployment

### Prerequisites

- Google Cloud account with billing enabled
- Python 3.13+
- `gcloud` CLI authenticated
- Gmail account with App Password (for email features)

### Quick Start

```bash
# Clone
git clone https://github.com/hmshimanyula1995/google-hackathon-2026.git
cd google-hackathon-2026

# Environment
cp .env.example .env
# Edit .env: GOOGLE_CLOUD_PROJECT, GOOGLE_GENAI_USE_VERTEXAI=True

# Dependencies
pip install -r requirements.txt

# Knowledge base (run locally — YouTube blocks datacenter IPs)
python3 -m pipeline.01_fetch_transcripts --priority P0
python3 -m pipeline.03_chunk_and_embed
python3 -m pipeline.04_ingest_firestore --clear

# Gmail setup (optional — for email features)
# 1. Enable 2FA at myaccount.google.com/security
# 2. Create app password at myaccount.google.com/apppasswords
# 3. Store in Secret Manager:
echo -n "your-app-password" | gcloud secrets create GMAIL_APP_PASSWORD --data-file=-

# Run
python3 main.py
# Open http://localhost:8000
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | `next-live-agent` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Yes | `us-central1` | GCP region |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `True` | Use Vertex AI backend |
| `GMAIL_APP_PASSWORD` | No | (Secret Manager) | Gmail app password for emails |
| `INVITATION_EMAIL` | No | (built-in) | Fallback recipient for invitation and itinerary emails |
| `PORT` | No | `8000` / `8080` | Server port |

### Deploy to Cloud Run

```bash
./deploy.sh   # One-command deployment
```

Settings: 2 CPU, 4GB RAM, session affinity, 3600s timeout, no-cpu-throttling, min-instances=1.

---

## Project Structure

```
├── main.py                           # FastAPI: REST + 2 WebSocket + A2A routes
├── requirements.txt                  # Dependencies (no external email SDK)
├── Dockerfile                        # Python 3.13-slim container
├── deploy.sh                         # Cloud Run deployment script
├── cloudbuild.yaml                   # CI/CD pipeline
│
├── next25_agent/                     # Alex — keynote presenter
│   ├── agent.py                      # Root agent + callbacks + vision agent
│   └── tools/
│       ├── search_tool.py            # Firestore vector search
│       ├── image_tool.py             # Imagen slide generation
│       ├── a2a_search_tool.py        # A2A search wrapper
│       └── a2a_slide_tool.py         # A2A slide wrapper
│
├── concierge_agent/                  # Maya — travel concierge
│   └── agent.py                      # Agent + confirm_booking + itinerary email
│
├── concierge_tools/                  # Maya's tools
│   ├── hotel_tool.py                 # A2A → HotelAgent
│   ├── flight_tool.py                # A2A → FlightAgent
│   └── invitation_tool.py            # Imagen card + Gmail SMTP email
│
├── hotel_agent/                      # A2A hotel search (google_search)
├── flight_agent/                     # A2A flight search (google_search)
│
├── static/
│   ├── index.html                    # 3-stage journey UI
│   ├── keynote.html                  # Standalone keynote (Alex only)
│   ├── css/style.css                 # Dark glassmorphic theme
│   └── js/
│       ├── app.js                    # 3-stage client + image upload
│       ├── keynote.js                # Standalone keynote client
│       ├── pcm-player-processor.js   # AudioWorklet: 24kHz playback
│       └── pcm-recorder-processor.js # AudioWorklet: 16kHz recording
│
└── pipeline/                         # Knowledge base ingestion
    ├── 01_fetch_transcripts.py
    ├── 03_chunk_and_embed.py
    ├── 04_ingest_firestore.py
    └── sources.py
```

---

## Models

| Component | Model | Purpose |
|-----------|-------|---------|
| Alex + Maya | `gemini-live-2.5-flash-native-audio` | Real-time voice (GA) |
| Hotel/Flight | `gemini-2.5-flash` | A2A text agents with google_search |
| Images | `imagen-4.0-fast-generate-001` | Invitations + slides (~2-5s) |
| Embeddings | `text-embedding-005` | 768-dim vectors for RAG |

## Third-Party

| Service | Purpose |
|---------|---------|
| **Gmail SMTP** | Invitation + itinerary emails (via App Password in Secret Manager) |

---

## Roadmap

The hackathon build works end to end but was written for one demo session at a time. Planned work:

- [ ] **Per-session state.** The tool guards (`_flight_searched`, `_hotel_searched`) and the slide queue are module-level globals shared by every connected user. Move them into ADK session state so concurrent visitors don't interfere with each other.
- [ ] **Test suite.** There are no automated tests yet. Add pytest coverage for the concierge tools, the A2A hotel/flight agents, the RAG search tool and the WebSocket handlers (with the Live API mocked).
- [ ] **Lock down the invitation endpoint.** `POST /api/invitation` sends email to any address it receives. Add rate limiting and bot protection, and stop writing raw email addresses to logs.
- [ ] **Configuration cleanup.** Remove hard-coded sender/recipient defaults and read them from environment variables or Secret Manager, documented in `.env.example`.
- [ ] **Refresh the knowledge base.** Re-run the pipeline on Google Cloud Next '26 sessions and make the event (name, dates, city) configurable instead of hard-coded to Next '25 in Las Vegas.
- [ ] **CI quality gates.** Add ruff and mypy, and run the tests in `cloudbuild.yaml` before deploying.

---

## Team

**Micheal Hudson Shimanyula** — [github.com/hmshimanyula1995](https://github.com/hmshimanyula1995)

## License

[MIT](LICENSE) © 2026 Micheal Hudson Shimanyula

Originally created for the Gemini Live Agent Challenge; the entrant retains IP under the contest rules (Section 12).
