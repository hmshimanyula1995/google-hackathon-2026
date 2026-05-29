---
description: Python conventions, async safety, type hints.
---

# Core rules

## Type hints
- Type hints on every function signature.
- Type hints on non-trivial locals (especially around async, websockets, GCP SDK calls).

## Async safety
- All async coroutines must be `await`ed.
- Don't fire-and-forget — wrap in `asyncio.create_task()` only when you handle the exception.
- WebSocket handlers must clean up on disconnect (close streams, cancel tasks, clear session queues).

## Exception handling
- Catch specific exceptions, never bare `except:`.
- Log GCP API errors with enough context to debug (operation name, request ID).

## Dependencies
- `google-adk`, `google-genai`, `google-cloud-firestore` are the core SDKs. Don't add a parallel one.
- Pin versions in `requirements.txt`.

## Verification before "ready"
1. `python3 main.py` boots without errors.
2. The specific WebSocket or REST flow you changed works locally (test in browser).
3. If you changed pipeline code: dry-run on a small subset before running the full ingestion.
