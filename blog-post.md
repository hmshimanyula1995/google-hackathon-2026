# What If Google Cloud Next Was Run by AI Agents? We Built It.

*Building a multi-agent conference experience with Google ADK, Gemini Live API, A2A Protocol, and 8 Google Cloud services*

**#GeminiLiveAgentChallenge**

*This project was built for the Gemini Live Agent Challenge hackathon on Devpost.*

---

Every year, Google Cloud Next brings together tens of thousands of developers in Las Vegas. There are 700+ sessions, 231 announcements, and three days of non-stop content. But behind the scenes, there's an enormous logistics machine that makes it all happen — from the moment you receive your invitation email to the moment a presenter walks on stage and delivers a keynote.

We asked ourselves: **what if that entire journey — invitation, travel booking, and keynote presentation — was powered by AI agents working together?**

Not a chatbot. Not a text box. A living, breathing system of AI agents that communicate with each other, see and generate images, hear your voice, speak back naturally, and coordinate in real-time to deliver the full Google Cloud Next experience.

That's what we built. We call it **Next Live**.

---

## The Problem: Conference Logistics is a Human Assembly Line

Think about what happens when you attend Google Cloud Next:

1. **You receive an invitation email** — usually with a ticket discount, event details, dates. Someone at Google designed that email, someone sent it.
2. **You book your travel** — you search flights from your city to Las Vegas, compare prices, find hotels near the Las Vegas Convention Center. You might call a travel agent, or spend hours on booking sites. Either way, a human is coordinating this.
3. **You attend the keynote** — a human presenter walks on stage with a slide deck. They present, they tell stories, they take questions from the audience. Behind them, someone advances the slides.

Every step involves humans coordinating with other humans. There are invitation systems, travel coordination, presentation teams, slide operators. It's a well-oiled machine — but it's a machine made of people.

**What if each of those humans was an AI agent? And what if those agents could talk to each other?**

That's not science fiction anymore. With Google's Agent Development Kit (ADK), the Gemini Live API, and the Agent-to-Agent (A2A) protocol, we built exactly that.

---

## The Solution: 5 AI Agents Running Google Cloud Next

Next Live is a **3-stage interactive AI experience** that mirrors the real conference journey:

### Stage 1: The Invitation

It all begins the same way it does in real life — with an email.

The user enters their email address on our landing page. An AI-powered invitation agent uses **Imagen 4.0** to generate a beautiful, unique invitation card for Google Cloud Next 2026. The card is rendered on screen and simultaneously sent to their inbox via email.

This is the moment of excitement. You've been invited. Now what?

### Stage 2: The Travel Concierge (Maya)

This is where it gets interesting. You click "Call Travel Concierge" and you're connected to **Maya** — a voice-powered AI travel agent.

Maya greets you warmly. She asks where you'll be flying from. You say "Chicago" — out loud, with your voice. Maya responds in a natural, conversational voice (powered by Gemini's native audio through the Live API):

> *"Chicago, great! Let me pull up some flights for you right now."*

Behind the scenes, Maya doesn't search for flights herself. She sends a request to the **FlightAgent** — a separate AI agent — using the **A2A (Agent-to-Agent) protocol**. The FlightAgent uses Google Search grounding to find real, current flight options from Chicago to Las Vegas. Real airlines. Real prices. Real departure times.

Maya presents the options conversationally: *"I found three nonstop options — Spirit for around $150, Frontier for about $155, or Southwest for a bit more. Which sounds good?"*

You pick one. Maya then asks about hotel preferences. She sends another A2A request to the **HotelAgent**, which searches for real hotels near the Las Vegas Convention Center. You discuss options. You pick a hotel.

But Maya doesn't just hear you — **she can see too.** During the conversation, you can share a photo of a hotel you found online. Maya analyzes the image, identifies the property, describes what she sees — "Oh nice, that looks like the Bellagio! Great pool area" — and works it into the booking conversation. See, Hear, and Speak — all three modalities in one agent.

Maya confirms the booking, generates an itinerary card on your screen, and sends a confirmation email to your inbox. Two agents (Hotel and Flight) collaborated with Maya through the A2A protocol to make this happen — just like real travel coordination, but with AI agents talking to each other.

### Stage 3: The Keynote (Alex)

Now comes the main event. You click "Join Keynote" and meet **Alex** — an AI keynote presenter.

Alex is not a chatbot. Alex is a **performer**. He opens with a hook:

> *"Google Cloud Next '25. Thirty thousand developers. 231 announcements. Three days in Las Vegas. And one theme that changes everything. AI agents."*

Alex delivers a structured keynote presentation with six sections, just like a real human presenter would. While he speaks, another agent generates **keynote slides using Imagen 4.0** — beautiful 16:9 presentation visuals that appear on screen in real-time.

But here's what makes Alex special:

- **He's interruptible.** You can ask a question mid-sentence and he'll pivot naturally: *"Great thought — let me land this point and then I want to hear that."*
- **He's grounded in real data.** Every fact Alex states comes from a Firestore vector database containing 264 minutes of real Google Cloud Next '25 session transcripts. He searches before he speaks. No hallucinations.
- **He tracks context across turns.** If you've asked about both ADK and A2A, Alex will notice and connect them: *"You've been asking about both ADK and A2A — want me to show how they work together?"*
- **He has a slide operator.** The slide generation runs in parallel — Alex speaks while the slide is being generated, and it appears on screen seamlessly.

This is the meta-story: **Alex is an AI agent, built with ADK, explaining the AI agent ecosystem that was announced at the conference where ADK was launched.** When Alex describes ADK, he's using the very tool he's describing. When he talks about A2A protocol, his concierge colleague Maya just used that same protocol to book your flights.

---

## The Architecture: How It All Works

### 5 Agents, 2 A2A Connections, 8 Google Cloud Services

```
Stage 1: INVITATION (REST API)
  Browser → POST /api/invitation → Imagen 4.0 → Email via Gmail

Stage 2: TRAVEL BOOKING (Gemini Live API, real-time voice)
  Browser ←→ WebSocket → ConciergeAgent "Maya"
    → A2A JSON-RPC → HotelAgent (google_search grounding)
    → A2A JSON-RPC → FlightAgent (google_search grounding)
    → confirm_booking → itinerary card + confirmation email

Stage 3: KEYNOTE (Gemini Live API, real-time voice)
  Browser ←→ WebSocket → KeynoteAgent "Alex"
    → Firestore vector search (98 docs, 768-dim embeddings)
    → Imagen 4.0 slide generation (16:9 keynote slides)
    → Python callbacks (topic tracking, zero LLM cost)
```

### The Gemini Live API: Voice-First, Not Text-First

Both Maya and Alex use `gemini-live-2.5-flash-native-audio` — a Gemini model that natively processes and generates audio. This isn't text-to-speech. The model thinks in audio. The result is natural prosody, natural pauses, and the ability to be interrupted mid-sentence — just like a real human conversation.

We use bidirectional WebSocket streaming (BIDI mode) so audio flows both ways simultaneously. The user can start speaking while the agent is still talking, and the agent will detect this and stop naturally.

### The A2A Protocol: Agents Talking to Agents

When Maya needs flight options, she doesn't call a function directly. She sends an **A2A JSON-RPC 2.0 message** to the FlightAgent — a separate ADK agent mounted at its own endpoint (`/a2a/flight/`). The FlightAgent processes the request independently using `google_search` grounding (fetching real, live flight data), and returns results through the A2A Task response format.

This is significant because it demonstrates **multi-agent orchestration** where agents with different capabilities collaborate through a standard protocol. Maya orchestrates. Hotel and Flight agents specialize. They communicate through A2A — the very protocol that was announced at the conference Alex presents about.

### Firestore RAG: Grounding in Reality

Alex never fabricates facts. Before making any claim, he searches a Firestore vector database containing 98 document chunks from 4 priority Google Cloud Next '25 YouTube videos (264 minutes of content). Queries are embedded using `text-embedding-005` (768 dimensions) and matched using COSINE distance search.

If Alex doesn't find information in his knowledge base, he says so: *"I don't have that in my notes from Next, but here's what I do know..."*

### Zero-Cost Context Tracking

Instead of using additional LLM calls to track conversation context, we use **Python callbacks** (`before_agent_callback` and `after_agent_callback`). These run as plain Python code — no model invocation — and track which topics have been discussed, detect when related topics have been mentioned, and generate bridge suggestions. This keeps the system at 1 LLM call per turn.

---

## Google Cloud Services Used

| Service | What It Does in Our System |
|---------|---------------------------|
| **Gemini Live API** | Real-time bidirectional voice streaming for Maya and Alex — native audio, not TTS |
| **Agent Development Kit (ADK)** | Framework for all 5 agents — LlmAgent, FunctionTool, callbacks, A2A integration |
| **Cloud Run** | Hosts the FastAPI server with WebSocket support, session affinity, and 3600s timeout |
| **Firestore** | Vector knowledge base — 98 documents with 768-dim COSINE vector index |
| **Vertex AI Embeddings** | `text-embedding-005` for embedding search queries and document chunks |
| **Vertex AI Imagen** | `imagen-4.0-fast-generate-001` for invitation cards and keynote slides |
| **Cloud Build** | CI/CD pipeline — automated container builds and deployment |
| **Secret Manager** | Gmail app password stored securely, accessed by Cloud Run service account |

---

## Technical Challenges We Solved

### The Async Deadlock

Our A2A tool wrappers initially used synchronous HTTP calls (`httpx.Client`). But since the A2A agents are mounted on the **same server**, the synchronous call blocked the event loop, preventing the server from processing the very request it was waiting for. Classic deadlock.

**Fix:** We switched to `httpx.AsyncClient` with `await`, so the event loop stays free to process incoming A2A requests while the tool waits for the response.

### The Infinite Tool Loop

The Gemini Live API model sometimes called the same tool repeatedly instead of presenting the results. Despite explicit instruction guards ("NEVER call the same tool twice"), the model ignored them.

**Fix:** We implemented code-level caching in the tool functions. If `search_flights("Chicago", ...)` is called again within 120 seconds, it instantly returns the cached result. The model gets the same data and moves on.

### Audio Context Isolation

Transitioning from Maya's voice session to Alex's keynote broke the Web Audio API pipeline. The AudioContext from the concierge session became stale, and creating new worklet nodes on the same context failed silently.

**Fix:** We separated Alex onto a completely standalone page (`/keynote`) with its own HTML, JavaScript, and AudioContext. The "Join Keynote" button does a full page navigation — fresh browser context, fresh mic permission, proven audio pattern.

---

## The Bigger Picture

What we built is a proof of concept for something much larger. Imagine every conference, every corporate event, every training session powered by coordinating AI agents:

- An **invitation agent** that personalizes outreach based on the recipient's interests
- A **logistics agent** that books travel, arranges accommodation, and handles dietary requirements
- A **presentation agent** that delivers content grounded in real data, adapts to the audience's questions, and generates visuals in real-time
- A **networking agent** that connects attendees with shared interests

The tools exist today. ADK gives you the agent framework. A2A gives you the communication protocol. Gemini Live gives you the voice interface. Firestore gives you the knowledge base. Imagen gives you the visuals.

We just put them together.

---

## Try It Yourself

- **Live Demo:** [next-live-agent-338756532561.us-central1.run.app](https://next-live-agent-338756532561.us-central1.run.app)
- **Keynote Only:** [next-live-agent-338756532561.us-central1.run.app/keynote](https://next-live-agent-338756532561.us-central1.run.app/keynote)
- **GitHub:** [github.com/hmshimanyula1995/google-hackathon-2026](https://github.com/hmshimanyula1995/google-hackathon-2026)

Enter your email, get your invitation, talk to Maya, book your trip, and join Alex's keynote. The entire journey runs on Google Cloud.

---

*Built by Michael Hudson Shimanyula for the Gemini Live Agent Challenge. Powered by Google ADK, Gemini Live API, A2A Protocol, Cloud Run, Firestore, Vertex AI, Imagen 4.0, and Cloud Build.*

*#GeminiLiveAgentChallenge*
