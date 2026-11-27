# Final Project ECE1779
- A PII-sanitizing LLM proxy for multiple tenants. Every request goes through these steps:

## Team Decision
- **Decided (as in proposal)**
  - Provider + orchestration: DigitalOcean + Kubernetes (minikube → DOKS)
  - LLM: hosted low-cost API (gpt-oss-120b), with a fake LLM for local tests. No self-hosting.
  - App framework: FastAPI. UI tool: Streamlit.
  - Presidio official analyzer image. Placeholder swap is done in our proxy.
  - PostgreSQL with persistent storage (StatefulSet + DigitalOcean Volume, no managed DB)
  - Advanced features: Security (API keys, Secrets, HTTPS), External services (LLM API), CI/CD (GitHub Actions: tests on every PR; on merge to main, build, push to DigitalOcean Container Registry tagged by commit ID, and roll out to DOKS)
  - HTTPS: DigitalOcean load balancer with managed certificates (Cloudflare is a stretch goal)
  - PII entities: EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION, plus one custom Secrets/API key recognizer
  - Placeholder map retains users's PII stays **in memory, per request** (not persisted). Single-request only, since with multiple message against LLM we will need persistent.
  - Audit row is written in two steps: a pending row before the LLM call, updated after. If the first write fails, the request is refused.

## Owners
- **Workstreams** 

| Person | Area | Focus |
|---|---|---|
| Daniel | Security + UI | Check each request's API key. Limit how many requests a team can send. Keep passwords and keys out of code using Secrets. Turn on HTTPS. Build a light UI playground. Cloudflare if time permits. |
| Hira | LLM + PII | Find PII with Presidio, including our API-key detector. Swap PII for placeholders, call LLM, then put real values back. Measure how much PII we catch, using fake test data. |
| Ammar | App + deployment | Build main app that runs request steps in order. Package everything in Docker, run it on Kubernetes (minikube, then DOKS), and keep database data safe across restarts. |
| Son | Monitoring + ops | Design database tables for logs. Set up cloud alerts and an uptime check. Write queries for request counts, speed, and errors. Set up automatic test and build runs on GitHub. |

## 5-Week Plan

| Week | Goal | Deadlines |
|---|---|---|
| W1 Nov 3–8 (done) | Finalize owners and stack; write and merge the proposal. | **[15%] Sat Nov 7: proposal** (submitted) |
| W2 Nov 9–15 | Freeze interfaces. Local end-to-end on Docker Compose: app → Presidio → LLM → put values back → audit row. Migrations + CI. | |
| W3 Nov 16–22 | Local orchestrator → cloud live: replicas, persistent DB volume, Secrets, HTTPS, alerts + uptime check, eval numbers, UI. **Sun Nov 22: presentation feature freeze.** | Mon Nov 16: Team Health Check quiz (each person) |
| W4 Nov 23–29 | Presentation prep: demo script + backup clips, slides, rehearsal. Attend Lecture 11 on Nov 25 (all). | Mon Nov 23: 70–100-word intro (each person). Tue Nov 24: slides (identical file; only work done by this date may be shown) |
| W5 Nov 30–Dec 5 | Rehearsal + Q&A prep. Final README report (≤5000 words) + `ai-session.md`. Video on deployed system. Fresh-clone test. | **[10%] Wed Dec 2: presentation**, 6 min + 2 min Q&A, live demo (our slot 12:57–13:05). **[35%] Sat Dec 5, 11:59 PM: final submission**: repo, README, ai-session.md, 2–5 min video, credentials to TA (password in a separate email). Keep cluster up. |

## Deployment (Kubernetes)

Run everything from the repo root, after `doctl kubernetes cluster kubeconfig save promptveil`
(for local testing, use `minikube start` instead).

### Before running `kubectl apply`

These three aren't in the YAML files (secrets are kept out of git), so create them first:

    PGPASS=$(openssl rand -hex 16)
    kubectl create secret generic postgres-secret \
      --from-literal=POSTGRES_PASSWORD="$PGPASS" \
      --from-literal=DATABASE_URL="postgresql://proxy:$PGPASS@postgres:5432/proxy"
    unset PGPASS

    kubectl create secret generic llm-secret --from-literal=LLM_API_KEY="<DO model access key>"

    kubectl create configmap postgres-init \
      --from-file=01-schema.sql=docs/database/schema.sql \
      --from-file=02-metrics.sql=docs/database/metrics.sql \
      --from-file=03-seed-dev.sql=docs/database/seed-dev.sql

Then deploy:

    kubectl apply -f k8s/base/

The proxy image is `:latest`, which CD keeps pointing at the newest build of `main`,
so a manual apply never rolls back to an old version.

### After the first deploy: issue API keys

`api_keys` starts empty, so every request returns 401 until a key exists.
Tenants 1 and 2 come from `docs/database/seed-dev.sql`. Issue one key per tenant:

    kubectl exec deploy/proxy -- python -m app.services.keygen create --tenant 1
    kubectl exec deploy/proxy -- python -m app.services.keygen create --tenant 2

Each key is printed **once** and only its SHA-256 hash is stored, so save it right away. Check that it works:

    curl -X POST https://promptveil.online/v1/chat \
      -H "X-API-Key: <your key>" -H "Content-Type: application/json" \
      -d '{"prompt":"Email Jane at jane@example.com"}'

A valid key returns 200 with the reply; a missing or wrong key returns 401.
The load balancer only listens on HTTPS (443), and its certificate is for `promptveil.online`.
To test it before DNS points at it, use `https://<EXTERNAL-IP>` with `curl -k` (`kubectl get svc proxy` shows the IP).

### UI (Streamlit)

`k8s/base/ui.yaml` runs the UI (`ui/`) with its own HTTPS load balancer, at `https://app.promptveil.online`.
It reaches the API inside the cluster (`http://proxy:443`), so its requests do not go back out through Cloudflare.

The free registry tier allows one repository, so the UI image shares `promptveil-registry/app` under `ui-` tags.
To build and deploy it by hand:

    R=registry.digitalocean.com/promptveil-registry/app
    doctl registry login
    docker build -t $R:ui-latest ui/ && docker push $R:ui-latest
    kubectl apply -f k8s/base/ui.yaml
    kubectl rollout restart deployment/ui     # pulls the new ui-latest

One replica only: Streamlit keeps each browser session in memory on one pod.

### Continuous Deployment

Every merge to `main` runs `.github/workflows/ci.yml`: tests, then build and push
`registry.digitalocean.com/promptveil-registry/app:<commit ID>` (and `:latest`),
then apply the app manifests and roll the `proxy` deployment to that commit's image.
The UI goes the same way as `app:ui-<commit ID>` (and `:ui-latest`), rolled out to the `ui` deployment.

    kubectl rollout history deployment/proxy   # what is running
    kubectl rollout undo deployment/proxy      # back to the previous commit

Notes:
- Without `postgres-init`, `postgres-0` stays stuck in `ContainerCreating`.
- The init SQL runs only on an empty volume. After a schema change: `kubectl delete pvc data-postgres-0` (this wipes the data).
- A load balancer's type can't be changed after it is created. If a Service's LB comes up as `REGIONAL_NETWORK`
  (Cloudflare shows 525), `kubectl delete svc <name>` and apply it again. This gives a new IP, so update the Cloudflare A record.

