# Project Proposal - {Name of Project}: {One line description}
Our team members:

|Name|Student Number|Email|
|:--:|:---:|:--:|
|Daniel Nolfi|1006018131|daniel.nolfi@mail.utoronto.ca|
|Hira Irfan|1008603370|hira.irfan@mail.utoronto.ca|
|Muhammad Ammar Mustafa|1005499970|a.mustafa@mail.utoronto.ca|
|Son Le|1011809893|sontung.le@mail.utoronto.ca|

## Motivation
Large language models (LLMs) are now part of everyday work: staff paste customer emails into chatbots to draft replies, send support tickets for summarization, and developers connect LLM APIs directly to internal tools. Each of these requests sends raw text to a third-party provider, and that text often contains personal information (names, email addresses, phone numbers, credit card numbers) as well as secrets such as API keys pasted alongside code. Once a prompt leaves the organization, the organization no longer controls where it is logged, how long it is kept, or who can see it. This risk is real: in 2023, Samsung restricted employee use of generative AI after engineers pasted confidential source code into ChatGPT.

### Problem Statement
Organizations want the productivity of hosted LLMs, but lack a simple, enforceable way to stop sensitive data from leaving with each request, and have no record of what was sent.

### Target Users
- **Application developers** who build LLM features into internal tools and need privacy protection without changing every application.
- **Teams or client organizations (tenants)** that share one gateway, each with its own API keys, usage limits, and isolated records.
- **Administrators and compliance staff** who must show that personal data was not disclosed, and need an audit trail that does not itself become a store of sensitive data.
- **The people whose data appears in prompts**, such as customers and employees, who never agreed to share it with an AI provider.

### Technical Motivation & Value
Privacy laws such as Canada's PIPEDA and the EU's GDPR hold organizations responsible for personal information they disclose to third parties, and a single leaked credential can compromise an entire system. Protection that relies on every person remembering to redact text by hand does not hold up in practice. It needs to happen automatically, at a single point that all LLM traffic passes through.

**Limitations of Existing Approaches:**
- **Banning AI tools** gives up the productivity benefit and risks pushing usage to unmonitored personal accounts.
- **Provider privacy commitments** (e.g., not training on business data) govern what happens after data has already left; they do not prevent the disclosure itself.
- **Manual redaction** is slow, inconsistent, and easy to forget.
- **Self-hosting an LLM** keeps data in-house but requires costly GPU infrastructure and ongoing operations that small teams cannot justify.
- **Simple redaction** (replacing PII with `[REDACTED]`) protects data but degrades answers, since the model's response can no longer refer to the right person or account.

Our project targets this gap: a shared, always-available gateway that removes PII (Personally Identifiable Information) before a request leaves, uses reversible placeholders so answers stay useful, restores real values only on the way back, and keeps a persistent audit log of what was detected, without storing the sensitive content itself. The gateway must be reliable, scalable, and stateful, which makes it a natural fit for a cloud-native deployment.

---

## 2. Objectives, Architecture, and Key Features 
### Objectives (Daniel)
{A paragraph of objectives here}

{A section of in-scope vs. out-of-scope}

### Technical Stack & Architecture (Ammar)
{List our technical decisions (cues from README.md here)}

### Key Features (Hira)
#### Core Features

#### Advanced Features 
{List 2 or more picked advanced features here}

---

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
