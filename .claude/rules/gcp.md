---
description: GCP / Cloud Run / Firestore / Vertex AI patterns. Performance budget protection.
paths:
  - "main.py"
  - "next25_agent/**"
  - "concierge_agent/**"
  - "concierge_tools/**"
  - "hotel_agent/**"
  - "flight_agent/**"
  - "pipeline/**"
  - "deploy.sh"
  - "cloudbuild.yaml"
---

# GCP & performance

## Performance budget (preserve at all costs)
- **1 LLM call per turn** for the keynote agent. Don't reintroduce `AgentTool` chains.
- **Zero-LLM context tracking** via Python callbacks (`before_agent`, `after_agent`).
- **Audio buffer instant-clear on interruption** — custom AudioWorklet on the frontend, backend cooperates.
- **50-70 word presentation bursts** — keeps interruptibility tight.
- **Session-scoped queues** — never share state between sessions.
- **A2A agents mounted in-process** — don't split into separate Cloud Run services.

## Vertex AI / Firestore
- Vector index on `session_chunks`: 768-dim COSINE.
- Embedding model: `text-embedding-005`. Changing this requires re-ingesting all 98 chunks.
- Don't introduce a second collection with a different schema without a migration plan.

## Models — production GA only
| Use case | Model |
|---|---|
| Live audio (keynote, concierge) | `gemini-live-2.5-flash-native-audio` |
| Text agents (hotel, flight) | `gemini-2.5-flash` |
| Image generation | `imagen-4.0-fast-generate-001` |
| Embeddings | `text-embedding-005` |

Don't swap to preview models without proposing first — the live audio model is the ONLY GA option for what we need.

## Cloud Run cost discipline
- Scale `min-instances` to 0 between work sessions:
  ```bash
  gcloud run services update next-live-agent --min-instances 0 --region us-central1
  ```
- Scale back before demos:
  ```bash
  gcloud run services update next-live-agent --min-instances 1 --region us-central1
  ```

## Deploy
- `./deploy.sh` is the canonical deploy path.
- `cloudbuild.yaml` defines CI/CD.
- Don't `gcloud builds submit` ad-hoc.
