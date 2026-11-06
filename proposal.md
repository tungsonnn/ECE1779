# Project Proposal - {Name of Project}: {One line description}
Our team members:

|Name|Student Number|Email|
|:--:|:---:|:--:|
|Daniel Nolfi|1006018131|daniel.nolfi@mail.utoronto.ca|
|Hira Irfan|1008603370|hira.irfan@mail.utoronto.ca|
|Muhammad Ammar Mustafa|1005499970|a.mustafa@mail.utoronto.ca|
|Son Le|1011809893|sontung.le@mail.utoronto.ca|

## 1. Motivation
Large language models (LLMs) are now part of everyday work: staff paste customer emails into chatbots to draft replies, 
send support tickets for summarization, and developers connect LLM APIs directly to internal tools. Each of these requests sends raw text to a third-party provider, 
and that text often contains personal information (names, email addresses, phone numbers, credit card numbers) as well as secrets such as API keys pasted alongside code. 
Once a prompt leaves the organization, the organization no longer controls where it is logged, how long it is kept, or who can see it. 
This risk is real: in 2023, Samsung restricted employee use of generative AI after engineers pasted confidential source code into ChatGPT.

### Problem Statement
Organizations want the productivity of hosted LLMs, but lack a simple, enforceable way to stop sensitive data from leaving with each request, and have no record of what was sent.

**Why it matters:** Privacy laws such as Canada's PIPEDA and the EU's GDPR hold organizations responsible for personal information they disclose to third parties, 
and a single leaked credential can compromise an entire system. Protection that relies on every person remembering to redact text by hand does not hold up in practice. 
It needs to happen automatically, at a single point that all LLM traffic passes through.

### Target Users
- Application developers who build LLM features into internal tools and need privacy protection without changing every application.
- Teams or client organizations (tenants) that share one gateway, each with its own API keys, usage limits, and isolated records.
- Administrators and compliance staff who must show that personal data was not disclosed, and need an audit trail that does not itself become a store of sensitive data.
- The people whose data appears in prompts, such as customers and employees, who never agreed to share it with an AI provider.

### Existing approaches limitations
- Banning AI tools gives up the productivity benefit and risks pushing usage to unmonitored personal accounts.
- Provider privacy commitments (e.g., not training on business data) govern what happens after data has already left; they do not prevent the disclosure itself.
- Self-hosting an LLM keeps data in-house but requires costly GPU infrastructure and ongoing operations that small teams cannot justify.
- Simple redaction (replacing personally identifiable information (PII) with [REDACTED]) protects data but degrades answers, 
since the model's response can no longer refer to the right person or account.

Our project fills this gap: a shared gateway that removes PII before a request leaves, restores it on the way back, 
and audits without storing content. Because all tenants depend on it, it must be reliable and stateful, a natural fit for cloud-native deployment.

---

## 2. Objectives, Architecture, and Key Features 
### Objectives 
Build a stateful, cloud-native proxy that removes PII from every prompt before it reaches a hosted LLM, using Presidio plus a custom API-key detector; 
restores real values in  the reply; keeps a per-tenant audit log that never stores content;  and runs reliably on DigitalOcean Kubernetes with monitoring and alerts.

### Architecture 
The system is a multi-tenant HTTPS proxy between client applications and a hosted LLM. 
All components run as containers on DigitalOcean Kubernetes (DOKS); only LLM is external.

```text
      api.<domain>                          admin.<domain>
   [DO Load Balancer]                     [DO Load Balancer]
           |                                      |
 +---------|------- DOKS cluster (2-3 nodes) -----|---------+
 |         v                                      v         |
 |   Proxy x2 (stateless) <---- admin API ---- Streamlit UI |
 |     |            |                                       |
 |     v            v                                       |
 |   Presidio     PostgreSQL x1 (StatefulSet)               |
 |   Analyzer x2    +- PVC -> DigitalOcean Volume           |
 +-----|----------------------------------------------------+
       v
   Hosted LLM API (gpt-oss-120b)
```

**Request flow.** Each request is handled synchronously:
1. Authenticate the API key (stored only as a hash) and check the tenant's rate limit.
2. The Presidio Analyzer detects PII; the proxy replaces it with numbered placeholders (e.g. `<PERSON_1>`), keeping the mapping in memory for this request only.
3. The sanitized text goes to the LLM; real values are restored in the reply.
4. An audit row (tenant, entity counts, status, latency; never content) is written before replying.

The proxy fails closed: if PII detection or the database is unavailable, it returns 503 rather than forwarding unsanitized or unrecorded data. 
We rejected a queue-based design because PII would have to be stored while queued.
 
**Component and scaling.** Stateless components run two replicas, because redundancy only costs memory: FastAPI proxy and the Presidio Analyzer. 
Running Presidio as a separate service shares its memory-heavy NLP model across proxy replicas, 
and anonymization is done in the proxy because we need numbered, reversible placeholders that Presidio's Anonymizer service doesn't provide. 
The stateful database runs a single instance, since redundancy would require replication, which is beyond our scope.

**State and persistent storage.** PostgreSQL stores tenants, hashed API keys, rate-limit counters, and the audit log. 
It runs as a StatefulSet whose PersistentVolumeClaim is backed by a DigitalOcean Volume, so data survives pod restarts and node rescheduling. 
Rate limits live in PostgreSQL, not per-pod memory, so the limit holds across replicas. Prompts, replies, 
and placeholder maps exist only in memory and are never written to the database or logs.

**Deployment.**
- Docker Compose runs the full stack locally with a fake LLM for development and tests.
- Kubernetes: developed on minikube, deployed to DOKS, with Kustomize overlays so both environments share one set of manifests. 
Nodes are sized so the cluster survives losing any one of them.
- Networking: the proxy and UI are exposed through DigitalOcean load balancers with managed HTTPS certificates; the Analyzer and database are internal only.
- CI/CD: GitHub Actions tests each pull request and pushes images, tagged by commit ID, to GitHub Container Registry
Secrets come from Kubernetes Secrets, never images.

**Monitoring.** DigitalOcean alerts on node CPU, memory, and disk, and uptime checks watch the public endpoints. 
A /health endpoint, checked by a DigitalOcean uptime monitor, alerts us when the database or Analyzer fails. 
The admin dashboard shows per-tenant requests, errors, latency, and PII caught, computed from the audit log.

### Key Features
#### Core Features
1. Multi-tenant access: each team (tenant) uses its own API key, and its usage and audit history are kept separate.
2. PII removal before the LLM: Presidio finds names, emails, phone numbers, credit card numbers, IP addresses and locations, 
and the proxy swaps each one for a numbered placeholder such as `<PERSON_1>`.
3. API key detection: a custom pattern detector also catches API keys and tokens pasted along with code.
4. Restored replies: placeholders in the LLM's reply are swapped back to the real values, so answers stay useful. 
The mapping exists in memory for one request only.
5. Audit log without content: each request records the tenant, PII counts, status and latency, never the prompt or reply.
6. Measured accuracy: using generated fake data, we report how much PII is caught for each type.
7. Demo and admin pages: a demo page shows a prompt before and after cleaning, and an admin page shows usage, errors and PII caught per tenant.

#### Advanced Features 
1. Security: hashed per-tenant API keys, Postgres-backed rate limits, Kubernetes Secrets, HTTPS via DO load-balancer certificates. 
With security via Cloudflare a stretch.
2. External service: a hosted LLM API (gpt-oss-120b), with a fake LLM for testing at no cost.
3. CI/CD: GitHub Actions tests every pull request and builds images on merge.

---

## 3. Project Plan & Team Responsibilities 
### Project Plan
| Week | Goal | Deadlines |
|---|---|---|
| 1 · Nov 3–8 | Team meeting: confirm owners, stack, volunteers; freeze interfaces. Proposal drafts, diagram, merge. Other work ad hoc. | Proposal, Nov 7 |
| 2 · Nov 9–15 | Local end-to-end on Docker Compose: app → Presidio → LLM → put values back → audit row. Migrations + CI. | |
| 3 · Nov 16–22 | Local orchestrator → cloud live: replicas, persistent DB volume, Secrets, HTTPS, alerts + uptime check, eval numbers, UI. | Health check, Nov 16 |
| 4 · Nov 23–29 | Presentation prep: demo script + backup clips, slides, rehearsal. | Intro, Nov 23; Slides, Nov 24 |
| 5 · Nov 30–Dec 5 | Rehearsal + Q&A prep. Final README report + `ai-session.md`. Video on deployed system. Fresh-clone test. | Present, Dec 2; Submission, Dec 5 |

### Team Responsibilities
| Person | Area | Focus |
|---|---|---|
| Daniel Nolfi | Security + UI | Check each request's API key. Limit how many requests a team can send. Keep passwords and keys out of code using Secrets. Enforce HTTPS. Implement a light UI playground. If time permits: Cloudflare WAF, rate limiting, DDoS protection, and up-to-date TLS ciphers. |
| Hira Irfan | LLM + PII | Find PII with Presidio, including our API-key detector. Swap PII for placeholders, call the LLM, then put real values back. Measure how much PII we catch, using fake test data. |
| Muhammad Ammar Mustafa | App + Deploy | Build the main app that runs the request steps in order. Package everything in Docker, run it on the chosen orchestrator and cloud, and keep database data safe across restarts. |
| Tung Son Le | Monitoring + Ops | Design database tables for logs. Set up cloud alerts and an uptime check. Write queries for request counts, speed, and errors. Set up automatic test and build runs on GitHub. |

**Integration**
- Freeze key interfaces before implementation: monitoring schema, secret names, Presidio call contract, and health endpoint.
- One request path ties the parts together: auth (Daniel) → scrub, LLM, restore (Hira) → audit row (Son's schema) → metrics and alerts (Son). Each step has a fixed input and output, so owners work in parallel against stubs.
- Docker Compose is the shared integration environment: everyone runs the stack with `docker compose up`.

**Dependencies**
- The app skeleton (Ammar) is the hub that Security, LLM + PII, and Monitoring plug into, so it comes first in Week 2.
- Alerts and the uptime check depend on the Week 3 cloud deploy and on `/health`.
- HTTPS depends on the hostname decision and ingress setup.
- The UI depends on the metrics queries and the request API.

**Risks and mitigations**
1. Presidio needs ~2 GB RAM → size nodes at ≥4 GB (covered by DO credits).
2. The LLM may alter placeholders (`<PERSON_1>`) → test it; fallback is to leave the placeholder as-is and log it.
3. Integration slips toward the slide deadline → feature freeze on Nov 22.

---
## 4. Initial Team Reasoning & AI-Assisted Exploration
### Initial Team Reasoning (Before Using AI)
**Architecture choices (early decisions and why)**  

**Anticipated challenges (what we expected to be hardest)**

**Early development approach (how we planned to build it)**

### AI-Assisted Exploration
**What was developed without AI assistance**
Before using AI tools, our team independently decided:
- [TBD]
- ...

**How AI tools contributed**
AI assistance was used to:
- [TBD]
- ...

**One specific AI-influenced idea and our team’s tradeoff discussion**
[TBD, similar to reasoning.md Q3 of our assignments]