# Final Project ECE1779
- A PII-sanitizing LLM proxy for multiple tenants. Every request goes through these steps:
 
- Auth -> Presidio detects PII and replaces it with placeholders (`<PERSON_1>`) -> Request goes to LLM 
  -> Real values are put back into the reply -> An audit row is written in log (metadata + entity counts only)
- Evaluation uses fake generated data
- Required stack: Docker, Docker Compose, PostgreSQL with persistent cloud storage, orchestration, monitoring.

## Team Decision
- **Recommendation**
  - Presidio official images (analyzer + anonymizer)
  - PostgreSQL with persistent storage (no managed DB)
  - Advanced features: Security (API keys, Secrets, HTTPS), External services (LLM API), CI/CD (minimal: GitHub Actions test + build/push)
  - PII entities: EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION, plus one custom Secrets/API key recognizer
  - Placeholder map retains users's PII stays **in memory, per request** (not persisted). Single-request only, since with multiple message against LLM we will need persistent.
- **To confirm at next team meeting**
  - Provider + orchestration: DigitalOcean + Kubernetes (minikube → DOKS) vs Fly.io + Docker Swarm
  - LLM: Self-host vs. low-cost LLM for ease of setup
  - HTTPS hostname (whether we use provided domain or a IP address with io, this based on Provider outcome)
  - UI tool: Streamlit (tentative) & App framework: FastAPI (tentative)
- **Later consideration, done by area expert member then share with team**
  - Secrets/API-key regex patterns
  - Shared interfaces: log table layout, env/secret names shared across stack, Presidio call contract, `/health` endpoint

## Owners
- **Proposal sections**
  1. Ammar: Motivation & Architecture
  2. Daniel: Objectives
  3. Hira: Key Features
  4. Son: Project Plan (and maybe Team Responsibility)
  5. All of us: Team Responsibilities, Reasoning and AI-assisted Exploration
- **Workstreams** (not final, need to confirm at team meeting for proposal)

| Person | Area | Focus |
|---|---|---|
| Daniel | Security | Check each request's API key. Limit how many requests a team can send. Keep passwords and keys out of  code using Secrets. Turn on HTTPS. |
| Hira | LLM + PII | Find PII with Presidio, including our API-key detector. Swap PII for placeholders, call LLM, then put real values back. Measure how much PII we catch, using fake test data. |
| Ammar | App + deployment | Build main app that runs request steps in order. Package everything in Docker, run it on chosen orchestrator and cloud, and keep database data safe across restarts. |
| Son | Monitoring + ops | Design database tables for logs. Set up cloud alerts and an uptime check. Write queries for request counts, speed, and errors. Set up automatic test and build runs on GitHub. |

- **Open tasks: UI and Slides** (outside main split)
  - UI = demo page + admin page.
  - Whoever volunteers hands part of their own area to others.

## 5-Week Plan
This, when have tentative approval, will become our project plan

| Week | Goal | Deadlines |
|---|---|---|
| W1 Nov 3–8 | Team meeting: confirm owners + stack + volunteers, freeze interfaces. Proposal drafts, diagram, merge. Other work ad hoc. | **[15%] Sat Nov 7, 11:59 PM: proposal**, every member submits identical file |
| W2 Nov 9–15 | Local end-to-end on Docker Compose: app → Presidio → LLM → put values back → audit row. Migrations + CI. | |
| W3 Nov 16–22 | Local orchestrator → cloud live: replicas, persistent DB volume, Secrets, HTTPS, alerts + uptime check, eval numbers, UI. **Sun Nov 22: presentation feature freeze.** | Mon Nov 16: Team Health Check quiz (each person) |
| W4 Nov 23–29 | Presentation prep: demo script + backup clips, slides, rehearsal. Attend Lecture 11 on Nov 25 (all). | Mon Nov 23: 70–100-word intro (each person). Tue Nov 24: slides (identical file; only work done by this date may be shown) |
| W5 Nov 30–Dec 5 | Rehearsal + Q&A prep. Final README report (≤5000 words) + `ai-session.md`. Video on deployed system. Fresh-clone test. | **[10%] Wed Dec 2: presentation**, 6 min + 2 min Q&A, live demo (our slot 12:57–13:05). **[35%] Sat Dec 5, 11:59 PM: final submission**: repo, README, ai-session.md, 2–5 min video, credentials to TA (password in a separate email). Keep cluster up. |
