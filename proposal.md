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

1. **Multi-tenant access:** each team (tenant) uses its own API key, and its usage and audit history are kept separate.
2. **PII removal before the LLM:** Presidio finds names, emails, phone numbers, credit card numbers, IP addresses and locations, and the proxy swaps each one for a numbered placeholder such as `<PERSON_1>`.
3. **API key detection:** a custom pattern detector also catches API keys and tokens pasted along with code.
4. **Restored replies:** placeholders in the LLM's reply are swapped back to the real values, so answers stay useful. The mapping exists in memory for one request only.
5. **Audit log without content:** each request records the tenant, PII counts, status and latency, never the prompt or reply.
6. **Measured accuracy:** using generated fake data, we report how much PII is caught for each type.
7. **Demo and admin pages:** a demo page shows a prompt before and after cleaning, and an admin page shows usage, errors and PII caught per tenant.

#### Advanced Features

1. **Security:** per-tenant API keys (stored as hashes), rate limits, Secrets and HTTPS, as described in the Security paragraph above.
2. **External service:** a hosted LLM API (gpt-oss-120b), with a fake LLM for testing at no cost.
3. **CI/CD:** GitHub Actions tests every pull request and builds images on merge.

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
