# Next Live — Real-time AI Keynote Presenter

Gemini Live Agent Challenge (Devpost) submission. Real-time AI keynote presenter for Google Cloud Next '25.

- **Deadline**: March 16, 2026 @ 5:00 PM PT
- **Repo**: github.com/hmshimanyula1995/google-hackathon-2026
- **Live URL**: https://next-live-agent-338756532561.us-central1.run.app

## GCP project
| Field | Value |
|---|---|
| Project ID | `next-live-agent` |
| Project Number | `338756532561` |
| Account | `admin@infinityedgetech.com` |
| Org | `infinityedgetech.com` (376212625743) |
| Region | `us-central1` |
| Firestore | Native mode, vector index on `session_chunks` (768-dim COSINE) |
| Enabled APIs | Firestore, Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Generative Language, Datastore |

## Architecture — 3-stage journey

```
Stage 1: INVITATION (REST API, no voice)
  Landing → POST /api/invitation → InvitationTool generates Imagen card
  → UI shows invitation + "Call Travel Concierge" button

Stage 2: TRAVEL BOOKING (Live API voice, interruptible)
  → WebSocket /ws/concierge/{session_id}
  → ConciergeAgent (Maya, voice: Aoede)
    → A2A JSON-RPC → HotelAgent (mounted at /a2a/hotel)
    → A2A JSON-RPC → FlightAgent (mounted at /a2a/flight)
  → Itinerary card on UI
  → "Confirm & Join Keynote" button

Stage 3: KEYNOTE (existing, reused session page)
  → WebSocket /ws/keynote/{session_id}
  → Alex (voice: Kore, keynote presenter)
    → search_next25_sessions() [FunctionTool]
    → generate_slide() [FunctionTool, Imagen 4.0 Fast]
    → Callbacks (before/after_agent, zero LLM cost)
  → Firestore Vector Search (session_chunks, 98 docs)
  → Vertex AI Embeddings (text-embedding-005, 768-dim)
  → Cloud Run (next-live-agent service)
```

5 agents (InvitationTool, ConciergeAgent Maya, HotelAgent, FlightAgent, Alex).
A2A connections: 2 (Concierge → Hotel, Concierge → Flight).
GCP services: 7 (Gemini Live, ADK, Cloud Run, Firestore, Vertex Embeddings, Imagen, Cloud Build).

## Models (production GA)
| Component | Model | Why |
|---|---|---|
| Alex (keynote) | `gemini-live-2.5-flash-native-audio` | Only live native audio model (GA) |
| Maya (concierge) | `gemini-live-2.5-flash-native-audio` | Same model, different voice (Aoede) |
| Hotel/Flight | `gemini-2.5-flash` | Text-only A2A, with `google_search` |
| Imagen | `imagen-4.0-fast-generate-001` | Fastest (~2-5s) |
| Embeddings | `text-embedding-005` | Production embedding, 768-dim |

## Key files
| File | Purpose |
|---|---|
| `main.py` | FastAPI server: A2A mounts, REST invitation, 2 WS endpoints |
| `next25_agent/agent.py` | Alex root_agent + callbacks + tools |
| `next25_agent/tools/search_tool.py` | Firestore vector search |
| `next25_agent/tools/image_tool.py` | Imagen slide generation |
| `concierge_agent/agent.py` | Maya + confirm_booking tool |
| `concierge_tools/hotel_tool.py` | A2A wrapper: Concierge → Hotel |
| `concierge_tools/flight_tool.py` | A2A wrapper: Concierge → Flight |
| `concierge_tools/invitation_tool.py` | Imagen invitation card |
| `hotel_agent/agent.py` | A2A hotel search (google_search grounding) |
| `flight_agent/agent.py` | A2A flight search (google_search grounding) |
| `static/` | Frontend: 3-stage UI |
| `pipeline/` | Data ingestion (transcripts → chunks → embed → Firestore) |
| `deploy.sh` | One-command Cloud Run deploy |
| `cloudbuild.yaml` | CI/CD pipeline |

## Performance budget (preserve)
- 1 LLM call per turn for keynote (removed AgentTool chain — don't reintroduce).
- Context tracking via Python callbacks (zero LLM cost).
- VAD: `prefix_padding_ms=0`, `start_of_speech_sensitivity=HIGH`.
- Audio buffer instant-clear on interruption (custom AudioWorklet).
- Presentation in 50-70 word bursts for interruptibility.
- Session-scoped queues prevent cross-session data leaks.
- A2A agents mounted in-process (no separate servers).

## Knowledge base
- 4 P0 YouTube videos: Developer Keynote, Opening Keynote, Introducing ADK, Keynote Highlights.
- 98 chunks in Firestore (2-min windows, 15s overlap).
- 264 minutes of conference content indexed.

## Commands
```bash
python3 main.py                                         # local server
./deploy.sh                                              # Cloud Run deploy
python3 -m pipeline.01_fetch_transcripts --priority P0   # fetch transcripts
python3 -m pipeline.03_chunk_and_embed                   # chunk + embed
python3 -m pipeline.04_ingest_firestore --clear          # ingest to Firestore
gcloud run services update next-live-agent --min-instances 0 --region us-central1   # scale down (save $$)
```

## Non-negotiables
- **Performance budget is hard.** Don't reintroduce extra LLM calls per turn. Maintain instant-clear interruption.
- **Cloud Run min-instances**: scale to 0 between work sessions to save money. Scale back up before demos.
- **Hackathon scope**: don't expand scope. Deadline is fixed (2026-03-16).
- **Firestore vector index** is 768-dim COSINE. Don't change the embedding model without re-ingesting all 98 chunks.
- **A2A agents mounted in-process** — don't break them into separate services without a strong reason.
- **GitHub account**: `hmshimanyula1995` — `gh auth switch --user hmshimanyula1995` before pushing.
- **Commits**: no Claude attribution.
- **Commit only when requested.**

## Where to look
- Detailed rules → `.claude/rules/`
- Deploy → `deploy.sh`
- CI/CD → `cloudbuild.yaml`
