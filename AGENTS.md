# CLAUDE.md — Next Live

**Project:** Next Live — Real-time AI voice agent for Google Cloud Next '25
**Hackathon:** Gemini Live Agent Challenge (Devpost)
**Deadline:** March 16, 2026 @ 8:00 PM EDT
**Repo:** github.com/hmshimanyula1995/google-hackathon-2026

---

## GCP Project

| Field | Value |
|---|---|
| **Project ID** | `next-live-agent` |
| **Project Number** | `338756532561` |
| **Account** | `admin@infinityedgetech.com` |
| **Org** | `infinityedgetech.com` (376212625743) |
| **Billing** | `01C19F-357B4C-0675EF` (Firebase Payment) |
| **Region** | `us-central1` |
| **Firestore** | Native mode, `(default)` database |
| **Enabled APIs** | Firestore, Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Generative Language, Datastore |

### GCP Auth Commands
```bash
gcloud config set project next-live-agent
gcloud config set account admin@infinityedgetech.com
```

---

## What This Is

A multimodal voice agent named "Alex" built with Google ADK that lets users have live, interruptible voice conversations about Google Cloud Next '25. Alex can hear (Live API audio), see (slide screenshots), and speak (native audio) — all grounded in real session transcripts stored in Firestore.

The meta-story: an AI agent built with ADK explains the ADK ecosystem announced at the conference where ADK launched.

## Tech Stack

| Component | Technology |
|---|---|
| Runtime | Python 3.13 |
| Agent framework | Google ADK (`google-adk >= 1.27.0`) |
| Voice model (root) | `gemini-live-2.5-flash-native-audio` (GA, Vertex AI) |
| Vision model | `gemini-2.5-pro` (GA) |
| Voice streaming | Gemini Live API — `StreamingMode.BIDI` |
| Embeddings | `text-embedding-005` (768-dim) via Vertex AI |
| Vector DB | Google Cloud Firestore (`session_chunks` collection) |
| Web framework | FastAPI + uvicorn (via ADK `get_fast_api_app`) |
| Hosting | Google Cloud Run |
| Data ingestion | `youtube-transcript-api`, `beautifulsoup4` |

## Project Structure

```
google-hackathorn/
├── next25_agent/                 # ADK agent package (required name for adk cli)
│   ├── __init__.py               # from . import agent
│   ├── agent.py                  # root_agent + all sub-agents
│   └── tools/
│       ├── __init__.py
│       └── search_tool.py        # Firestore vector search function
├── pipeline/                     # Data ingestion scripts (run locally, not deployed)
│   ├── sources.py                # Video IDs + blog URLs
│   ├── 01_fetch_transcripts.py
│   ├── 02_fetch_blogs.py
│   ├── 03_chunk_and_embed.py
│   ├── 04_ingest_firestore.py
│   └── data/                     # Raw data (gitignored)
│       ├── transcripts/
│       ├── blogs/
│       └── chunks/
├── main.py                       # FastAPI entry point for Cloud Run
├── Dockerfile
├── cloudrun.yaml
├── cloudbuild.yaml
├── deploy.sh
├── requirements.txt
├── .env                          # Local env vars (gitignored)
├── .env.example                  # Template for .env
├── .agent/                       # Internal docs — PRD, guides (gitignored)
├── CLAUDE.md                     # This file
├── AGENTS.md                     # Mirror of this file
└── README.md                     # Public-facing setup instructions for judges
```

## Environment Setup

### Prerequisites
- Python 3.13+
- Google Cloud SDK (`gcloud`) authenticated
- GCP project with: Firestore (native mode), Vertex AI API, Cloud Run API enabled

### Local Development
```bash
# Create venv
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment
cp .env.example .env  # Edit with your GCP project ID

# Run locally with ADK dev server
adk web next25_agent

# Run with voice (Live API)
adk web next25_agent --modality voice
```

### GCP Configuration
```bash
# Set project (already done — see GCP Project section above)
gcloud config set project next-live-agent
gcloud config set account admin@infinityedgetech.com

# APIs are already enabled. Firestore vector index is already created.
# To verify:
gcloud firestore indexes composite list --project=next-live-agent
```

### Pipeline (Run Locally Only)
```bash
# YouTube blocks datacenter IPs — always run transcript fetch from local machine
python pipeline/01_fetch_transcripts.py
python pipeline/02_fetch_blogs.py
python pipeline/03_chunk_and_embed.py
python pipeline/04_ingest_firestore.py
```

## Key ADK Patterns

### Agent Export Convention
ADK requires `root_agent` to be importable from the agent package:
```python
# next25_agent/__init__.py
from . import agent

# next25_agent/agent.py
root_agent = LlmAgent(name="alex", ...)  # MUST be named root_agent
```

### AgentTool Pattern (Not sub_agent Transfer)
All sub-agents are wrapped as `AgentTool` — the orchestrator (Alex) stays in control:
```python
from google.adk.agents import AgentTool

search_tool = AgentTool(agent=search_agent)
root_agent = LlmAgent(name="alex", tools=[search_tool, ...])
```
Never use `sub_agents=[]` transfer — it yields control and breaks persona continuity.

### Voice Configuration
```python
from google.adk.agents.run_config import RunConfig, StreamingMode

run_config = RunConfig(
    response_modalities=["AUDIO"],
    streaming_mode=StreamingMode.BIDI,
    speech_config={"voice_config": {"prebuilt_voice_config": {"voice_name": "Kore"}}},
)
```

### Session State Keys
| Key | Written By | Read By |
|---|---|---|
| `search_results` | SearchAgent | PresenterAgent, QAAgent |
| `presentation` | PresenterAgent | root_agent (Alex) |
| `qa_response` | QAAgent | root_agent |
| `vision_response` | VisionAgent | root_agent |
| `topics_asked` | ContextTrackerAgent | root_agent, QAAgent |
| `bridge_suggestion` | ContextTrackerAgent | root_agent |
| `final_response` | root_agent | Output |

## Firestore Schema

Collection: `session_chunks`

| Field | Type | Notes |
|---|---|---|
| `source_type` | string | `"youtube_transcript"` or `"blog_post"` |
| `source_id` | string | YouTube video ID or blog URL slug |
| `title` | string | Session or article title |
| `track` | string | `"ADK"`, `"Keynote"`, `"Customer Story"`, etc. |
| `speakers` | array | Speaker names (YouTube only) |
| `start_time` | int | Seconds from video start (YouTube only) |
| `youtube_url` | string | Full URL with timestamp parameter |
| `url` | string | Blog post URL (blogs only) |
| `raw_text` | string | Clean text — returned in search results |
| `text` | string | Prefixed text — used for embedding |
| `embedding` | Vector(768) | COSINE similarity — NOT returned in queries |

## Cloud Run Deployment

### Critical Settings (Non-Negotiable)
```bash
gcloud run deploy next-live-agent \
  --source . \
  --region us-central1 \
  --timeout 3600 \
  --cpu 2 \
  --memory 4Gi \
  --min-instances 1 \
  --max-instances 20 \
  --concurrency 80 \
  --no-cpu-throttling \
  --session-affinity \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=next-live-agent,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=True"
```

Every setting matters:
- `timeout 3600` — WebSocket sessions up to 60 min
- `no-cpu-throttling` — CPU stays allocated during audio gaps
- `session-affinity` — stateful sessions route to same instance
- `min-instances 1` — no cold starts during demo

## Development Rules

### Grounding (Zero Tolerance for Hallucination)
- Every factual claim must come from Firestore search results
- Agent instructions must include: "Never state any fact not present in search_results"
- If no results found, Alex says "I don't have that in my notes" — never guesses

### Alex Persona
- Name: Alex. POV: developer-attendee, not Google employee
- Voice: Kore. Max 150 words per response (~60 seconds audio)
- Ends with open invitation: "Want to go deeper on that?"
- Knowledge scope: Next '25 AI agent ecosystem ONLY

### Code Standards
- Python 3.13, type hints on all functions
- `try/except` on all Firestore calls
- No `any` types — strict typing
- Run `mypy` or type checker before completing tasks

### What NOT to Do
- Never use `sub_agents=[]` transfer — use `AgentTool` wrapper
- Never use TTS on top of text output — use native audio model
- Never run `youtube-transcript-api` on cloud VMs — YouTube blocks datacenter IPs
- Never deploy to AWS — this is GCP only
- Never hard-code GCP project IDs in source code — use env vars
- Never return embeddings in search results — they waste context window

## Git Rules
- Commit only when explicitly requested
- No automated signatures (no Co-Authored-By, no Claude attribution)
- `pipeline/data/` is gitignored (raw transcripts are large)
- `.agent/` is gitignored (confidential PRD and internal docs)
- `.env` is gitignored (credentials)

## Quick Reference

| Action | Command |
|---|---|
| Local dev server | `adk web next25_agent` |
| Local voice mode | `adk web next25_agent --modality voice` |
| Run pipeline step | `python pipeline/0X_*.py` |
| Deploy to Cloud Run | `./deploy.sh` or `adk deploy cloud_run` |
| Check Firestore index | `gcloud firestore indexes composite list` |
| Type check | `mypy next25_agent/ --ignore-missing-imports` |
