# Project Proposal - {Name of Project}: {One line description}
Our team members:

|Name|Student Number|Email|
|:--:|:---:|:--:|
|Daniel Nolfi|1006018131|daniel.nolfi@mail.utoronto.ca|
|Hira Irfan|1008603370|hira.irfan@mail.utoronto.ca|
|Muhammad Ammar Mustafa|1005499970|a.mustafa@mail.utoronto.ca|
|Son Le|1011809893|sontung.le@mail.utoronto.ca|

## 1. Motivation - (Ammar)
{Few lines summary}

### Problem Statement
{Can focus on how company have employees whom paste credentials to LLM}
### Target Users
{Company or personal user}
### Technical Motivation & Value
{Rising use of AI...}

---

## 2. Objectives, Architecture, and Key Features 
### Objectives (Daniel)
{A paragraph of objectives here}

{A section of in-scope vs. out-of-scope}

### Technical Stack & Architecture (Ammar)
{List our technical decisions (cues from README.md here)}

### Key Features (Hira)

#### Core Features

1. **Separate teams on one system.** Many teams (for example, different companies or departments) can use the gateway at the same time. Each team has its own API key, and its usage is tracked separately.
2. **PII-safe LLM requests.** A team sends a prompt to our gateway using its API key. Before anything leaves our system, the gateway uses Presidio to find personal data (names, emails, phone numbers, credit card numbers, IP addresses and locations) and swaps each one for a placeholder such as `<PERSON_1>`. Only the cleaned prompt is sent to the LLM.
3. **Real values put back.** When the LLM replies, the gateway swaps each placeholder back to its real value, so the user still gets a normal, useful answer. The list linking placeholders to real values is kept in memory for that one request only and is never saved.
4. **API key and secret detection.** On top of Presidio's built-in detectors, we add our own detector for API keys and tokens, because pasting code that contains a key into a chatbot is one of the most common leaks.
5. **Audit log without PII.** Every request adds one row to PostgreSQL with details only: which team sent it, when, how long it took, whether it worked, and how many of each PII type were found. Prompt text and PII are never stored.
6. **Measured detection quality.** We test the gateway with generated fake data, never real personal data, and report how much PII it catches for each type.
7. **Demo and admin pages.** A simple demo page shows a prompt before and after cleaning, and an admin page shows request counts, response times and errors from the audit log.

These features use every required technology. The gateway app, Presidio and PostgreSQL each run in their own Docker container, and Docker Compose runs them together during development. The audit log lives in PostgreSQL on a persistent volume, so no data is lost on restart. In the cloud, the system runs on DigitalOcean with Kubernetes (minikube locally, then DigitalOcean Kubernetes), with more than one copy of the gateway and Presidio so it stays up if one fails. For monitoring, we use DigitalOcean's metrics and alerts, an uptime check, and queries on the audit log for request counts, speed and errors.

#### Advanced Features

1. **Security enhancements.** Each team has its own API key, checked on every request, and a limit on how many requests it can send. Passwords and keys are stored as Kubernetes Secrets instead of in code, and all traffic uses HTTPS.
2. **Integration with an external service.** The gateway calls a hosted LLM API instead of running a model on our own servers, which would need expensive GPU machines. Our estimate puts the LLM cost for the whole project at a few dollars. For load testing, we switch to a mock LLM so tests cost nothing.
3. **CI/CD pipeline.** GitHub Actions runs our tests and builds and pushes the Docker images whenever code is merged into the main branch.

To keep the project doable in five weeks, each request is handled on its own (no chat history), and we focus on the six PII types above plus API keys.

## 3. Project Plan & Team Responsibilities 
### Project Plan (Son)
{Split our workload into 5 weeks chunk with final deadline of first week of December}
### Team Responsibilities

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
