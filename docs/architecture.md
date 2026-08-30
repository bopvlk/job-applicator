# Architecture

Agreed design for **Job Applicator (ApplyBot)** (pet project). Source of truth for structure and key decisions.

## Decisions (locked)

- **Infrastructure:** Hosted on AWS EC2 (t3.micro, Ubuntu). Databases are outsourced to managed cloud free tiers (CockroachDB Serverless & Qdrant Cloud) to save server RAM and CPU.
- **Relational DB (CockroachDB):** Used for strict state management (users, job URLs, application statuses). 
  - **No migrations, single source of truth = SQLModel.** `storage/models.py` (SQLModel table classes) IS the schema. `storage/db.py` runs `SQLModel.metadata.create_all(engine)` at startup via standard PostgreSQL dialect connection string. No `schema.sql`, no Alembic, no hand-mirrored classes.
  - Using standard Postgres integer types (`IDENTITY` or `BigInt` for IDs) for CockroachDB compatibility.
- **Vector DB (Qdrant):** Used for semantic search and deduplication.
- **Config = `config.yaml` + environment.** Non-secrets (lists, model name, interval) live in `config.yaml`; secrets (`telegram_token`, SMTP creds, DB URIs, Qdrant API keys) come from env vars via `pydantic-settings`. Env wins over yaml.
- **No PDF/CV ingestion for now.** The user types a free-text `desired_description` in Telegram (what they're actually looking for, not just a title); it's stored on `users` and used for **both** query generation (`queries.py`) **and** as the relevance rubric for `filter.py` (replaces `services/pdf.py` + CV-based `queries.py`).
- **OTP stored plaintext (6-digit).** Acceptable only for a single-user local pet project; documented `ponytail:` ceiling. Hash (salt + sha256, constant-time compare) if it ever goes multi-user/remote.
- **External clients live in `clients.py` (composition root).** All third-party API clients (Gemini, Tavily, Jina Reader, Qdrant Cloud) are constructed **once** from `Config` in `clients.py`; services import the ready client and never build their own. Keeps config/env coupling in one place (instead of scattering `Client(...)` across every service file).
- **research vs analysis are separate:**
  - `research.py` — discovery/ingestion: Tavily/SerpAPI find + Jina Reader fetch → raw postings. Cheap, high-volume.
  - `filter.py` — relevance gate between research and analysis. **MVP:** cheap Tavily `score` threshold (`config.min_tavily_score`, default 0.4) drops noise before any tokens are spent. **Next:** Gemini judge on `title`+`content` vs `users.desired_description` (see Roadmap).
  - `analysis.py` — evaluation: Gemini per-job scoring → strict JSON. Expensive, per unique (and already relevant) job.
  - Dedup (Qdrant Cloud) runs *between* research/filter and analysis so tokens aren't spent on duplicates.

## Structure

```text
src/job_applicator/
  __init__.py
  __main__.py              # entrypoint: build config, boot db + bot + scheduler
  cli.py                   # typer: run / etc.
  config.py                # pydantic-settings Config (config.yaml + env, env wins)
  clients.py               # composition root: external API clients (Gemini, Tavily, Jina, Qdrant)

  bot/
    __init__.py
    app.py                 # Bot + Dispatcher wiring, lifespan
    handlers/
      __init__.py
      auth.py              # /start, email, OTP FSM
      cv.py                # PDF upload
      jobs.py              # status inline keyboards

  services/
    __init__.py
    email.py               # aiosmtplib OTP send
    queries.py             # build search queries from users.desired_description (no PDF for now)
    research.py            # Tavily/SerpAPI find + Jina Reader fetch -> raw postings
    filter.py              # Gemini relevance judge: drop postings not matching desired_description
    analysis.py            # Gemini per-job scoring -> strict JSON
    # pdf.py (CV parse) -- DEFERRED until needed

  storage/
    __init__.py
    models.py              # SQLModel table classes (mapped to CockroachDB)
    db.py                  # engine + session; runs create_all at startup via Postgres dialect
    dedup.py               # Qdrant Cloud client (embeddings & semantic search)

  scheduler.py             # APScheduler loop: research -> filter -> dedup -> analysis

## MVP scope (current build)

First runnable pipeline:

  research (Tavily) -> filter (Tavily score gate ONLY) -> dedup (Qdrant) -> analysis (Gemini)

- `filter.py` MVP = single cheap gate: drop postings where Tavily `score` < `config.min_tavily_score`
  (default 0.4, tunable in `config.yaml`; env overrides). No Gemini call yet — the relevance judge is a
  stub (pass-through) so we can validate Tavily scores first.
- `min_tavily_score` is a non-secret tunable (lives in `config.yaml`, not env).

## Roadmap (post-MVP)

1. **Gemini relevance gate in `filter.py`.** Replace the stub with one batched Gemini call that scores
   each posting's `title`+`content` against `users.desired_description`; drop where Gemini score < 0.5.
2. **Two-gate approach (cheapest first).** Pre-filter Tavily `score` < ~0.2 (kills obvious noise, saves
   Gemini tokens), then run the Gemini judge on the remainder. Keeps the expensive step for relevant-only
   items.