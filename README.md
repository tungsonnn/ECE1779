# Final Project ECE1779
- A PII-sanitizing LLM proxy for multiple tenants. Every request goes through these steps:
 
- Auth -> Presidio detects PII and replaces it with placeholders (`<PERSON_1>`) -> Request goes to LLM 
  -> Real values are put back into the reply -> An audit row is written in log (metadata + entity counts only)
- Evaluation uses fake generated data
- Required stack: Docker, Docker Compose, PostgreSQL with persistent cloud storage, orchestration, monitoring.

## Team Decision
- **Decided (as in proposal)**
  - Provider + orchestration: DigitalOcean + Kubernetes (minikube → DOKS)
  - LLM: hosted low-cost API (gpt-oss-120b), with a fake LLM for local tests. No self-hosting.
  - App framework: FastAPI. UI tool: Streamlit.
  - Presidio official analyzer image. Placeholder swap is done in our proxy.
  - PostgreSQL with persistent storage (StatefulSet + DigitalOcean Volume, no managed DB)
  - Advanced features: Security (API keys, Secrets, HTTPS), External services (LLM API), CI/CD (minimal: GitHub Actions test + build/push to GitHub Container Registry)
  - HTTPS: DigitalOcean load balancer with managed certificates (Cloudflare is a stretch goal)
  - PII entities: EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION, plus one custom Secrets/API key recognizer
  - Placeholder map retains users's PII stays **in memory, per request** (not persisted). Single-request only, since with multiple message against LLM we will need persistent.
  - Audit row is written in two steps: a pending row before the LLM call, updated after. If the first write fails, the request is refused.
- **To confirm at next team meeting**
  - [Son] Log table layout, `/health` heartbeat check contract 
  - [Hira] Presidio call contract: what does service takes and returns (cleaned text, placeholder map, entity counts) and LLM provider for gpt-oss-120b
  - [Daniel] Env and secret names shared across the stack (database url, llm key,...), register a domain name for HTTPS certificates
  - [Ammar] App skeleton: one endpoint calling the step in order (authentication -> clean PII -> give to LLM -> restore PII -> audit), DigitalOcean setup
- **Later consideration, done by area expert member then share with team**
  - [Hira] Secrets/API-key regex PII patterns

## Owners
- **Workstreams** 

| Person | Area | Focus |
|---|---|---|
| Daniel | Security + UI | Check each request's API key. Limit how many requests a team can send. Keep passwords and keys out of code using Secrets. Turn on HTTPS. Build a light UI playground. Cloudflare if time permits. |
| Hira | LLM + PII | Find PII with Presidio, including our API-key detector. Swap PII for placeholders, call LLM, then put real values back. Measure how much PII we catch, using fake test data. |
| Ammar | App + deployment | Build main app that runs request steps in order. Package everything in Docker, run it on Kubernetes (minikube, then DOKS), and keep database data safe across restarts. |
| Son | Monitoring + ops | Design database tables for logs. Set up cloud alerts and an uptime check. Write queries for request counts, speed, and errors. Set up automatic test and build runs on GitHub. |

- **Dependencies**

| Blocked | Waiting On | Why |
|---|---|---|
| Everyone | Ammar: app skeleton + Compose |   It's the hub. It should be one endpoint calling five empty functions |
| Daniel (auth), Ammar (audit write) | Son: schema | Need to read and write to tables |
| Ammar (k8s files) | Working Compose stack| Same containers, nothing to deploy to K8s until compose runs |
| Son: alerts + health check| Ammar: DOKS live with public URL | Alerts attach to real nodes |
| Daniel: HTTPS feature| HTTPS domain + Ammar load balancer config| DO-managed certs need a domain |

Hira is blocked on nobody: PII sanitize and restore only need the Presidio container, so that can work today as standalone.

### Baseline for feature freeze

1. One command (docker compose up) starts everything locally: proxy, Presidio, Postgres, fake LLM.
2. One request works end to end: prompt in with an API key, PII swapped out, LLM called, real values put back.
3. Every request leaves one audit row with no prompt text.
4. Data survives a restart: delete the Postgres pod and the rows are still there.
5. The same stack runs on Kubernetes with 2 proxy copies, on minikube first and then DOKS.
6. DO alerts and one uptime check exist and can be shown.
7. The two advanced features can be shown: API key plus HTTPS, and one real LLM call.
8. One demo page shows a prompt before and after scrubbing.

- **Open task: Slides** (outside main split)
  - Whoever volunteers hands part of their own area to others.

## 5-Week Plan

| Week | Goal | Deadlines |
|---|---|---|
| W1 Nov 3–8 (done) | Finalize owners and stack; write and merge the proposal. | **[15%] Sat Nov 7: proposal** (submitted) |
| W2 Nov 9–15 | Freeze interfaces. Local end-to-end on Docker Compose: app → Presidio → LLM → put values back → audit row. Migrations + CI. | |
| W3 Nov 16–22 | Local orchestrator → cloud live: replicas, persistent DB volume, Secrets, HTTPS, alerts + uptime check, eval numbers, UI. **Sun Nov 22: presentation feature freeze.** | Mon Nov 16: Team Health Check quiz (each person) |
| W4 Nov 23–29 | Presentation prep: demo script + backup clips, slides, rehearsal. Attend Lecture 11 on Nov 25 (all). | Mon Nov 23: 70–100-word intro (each person). Tue Nov 24: slides (identical file; only work done by this date may be shown) |
| W5 Nov 30–Dec 5 | Rehearsal + Q&A prep. Final README report (≤5000 words) + `ai-session.md`. Video on deployed system. Fresh-clone test. | **[10%] Wed Dec 2: presentation**, 6 min + 2 min Q&A, live demo (our slot 12:57–13:05). **[35%] Sat Dec 5, 11:59 PM: final submission**: repo, README, ai-session.md, 2–5 min video, credentials to TA (password in a separate email). Keep cluster up. |

### Order of work
1. Freeze the schema and the function inputs and outputs at the meeting.
2. Skeleton with empty functions, by about Nov 16.
3. Everyone fills in their own function in parallel.
4. minikube.
5. DOKS.
6. Alerts and HTTPS.
7. Freeze on Nov 22 