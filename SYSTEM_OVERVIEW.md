# 🚀 Job Applicator AI — System Overview & Tech Stack

## 🎯 Main Purpose of the Project

**Job Applicator AI** is an autonomous, AI-powered recruitment agent that monitors the tech market 24/7. It searches for vacancies matching your exact seniority and stack, filters out catalog junk and duplicates, performs deep multi-factor technical analysis, and delivers high-match jobs directly to your Telegram with 3 on-demand tailored cover letter variants.

---

## ⚡ The Complete Pipeline Flow

```python
async def run_pipeline_for_user(user: User) -> None:
    """1. GENERATE SEARCH QUERIES BASED ON USER PROFILE"""
    queries = await build_queries(user.desired_title, user.top_skills)

    """2. SEARCH THE WEB & FETCH CLEAN MARKDOWN"""
    raw_postings = await search_tavily(queries, sites=["djinni.co", "dou.ua", ...])
    cleaned_postings = [await jina_fetch_markdown(p.url) for p in raw_postings]

    """3. SEMANTIC VECTOR DEDUPLICATION (Skip already seen jobs)"""
    unique_postings = await qdrant_dedup.filter_duplicates(cleaned_postings)

    """4. MULTI-FACTOR REASONING & QUALITY GATE (Gemini 2.5)"""
    for posting in unique_postings:
        result = await gemini.evaluate_job(posting, user_profile=user)

        # 🚫 Quality Gate: Discard catalog pages, outdated ads, or low scores
        if (
            not result.is_single_job_posting
            or not result.is_active_and_fresh
            or result.overall_match_score < user.min_match_score
        ):
            continue

        """5. SAVE TO COCKROACHDB & DISPATCH TELEGRAM CARD"""
        job = await db.save_job(user_id=user.telegram_chat_id, result=result)
        await telegram.send_job_card(chat_id=user.telegram_chat_id, job=job)
```

---

## 🛠️ Technology Stack Breakdown (Point by Point)

### 1. 🧠 Google Gemini 2.5 Flash (`google-genai`)
* **Role:** Multi-Factor Evaluation, Multimodal Ingestion & On-Demand Copywriting.
* **Why chosen:**
  * **Native Multimodal PDF Parsing:** Ingests your uploaded `.pdf` resume in Telegram and extracts your skills/achievements with zero third-party OCR tools.
  * **Ultra-Fast TypedDict JSON Output:** Returns structured schemas via standard Python `TypedDict` and `json.loads()`, running 2.5x faster with minimal memory overhead.
  * **Sub-second Latency & Low Cost:** Generates 3 targeted cover letter styles in < 1.5 seconds.

### 2. 🔍 Tavily Search API
* **Role:** Real-Time Tech Job Discovery.
* **Why chosen:** Purpose-built for AI agents; searches specific job domains (`djinni.co`, `dou.ua`, `linkedin.com`) with `time_range="week"` to guarantee fresh, active postings.

### 3. 📄 Jina AI Reader (`r.jina.ai`)
* **Role:** Web Scraper & HTML-to-Markdown Converter.
* **Why chosen:** Converts messy vacancy web pages filled with banners, navigation bars, and JavaScript into clean, token-efficient Markdown for LLM analysis.

### 4. 🧭 Qdrant Cloud (Vector Database)
* **Role:** Semantic Deduplication.
* **Why chosen:** Converts vacancy text into vector embeddings. If the same job is reposted with slight wording changes or across multiple aggregators, cosine similarity (`>= 0.85`) detects and drops it before wasting LLM tokens.

### 5. 🗄️ CockroachDB Serverless (SQLModel / PostgreSQL)
* **Role:** Relational Database & Strict State Management.
* **Why chosen:** Cloud-native, zero-maintenance Postgres-compatible SQL database storing users, candidate profiles, and job application lifecycles (`NEW` → `APPLIED` → `REJECTED`).

### 6. 🤖 Aiogram 3.x (Async Telegram Bot)
* **Role:** User Interface & Interactive Action Center.
* **Why chosen:**
  * **FSM (Finite State Machine):** Manages email OTP login and `/upload_resume` PDF flows.
  * **Inline Action Buttons:** One-tap interaction (`[ 📝 Generate Cover Letters ]`, `[ ✅ Applied ]`, `[ ❌ Reject ]`).
  * **Live Commands:** Instant on-demand search (`/search_now`), profile dashboard (`/profile`), and settings (`/set_skills`, `/set_salary`, `/set_min_score`).

### 7. ⏰ APScheduler
* **Role:** Background Cron Runner.
* **Why chosen:** Runs non-blocking asynchronous job hunts every 30 minutes in the background without freezing the Telegram bot.

### 8. ☁️ AWS EC2 & Systems Manager (SSM)
* **Role:** Production Cloud Hosting & Zero-Disk Secret Management.
* **Why chosen:**
  * Hosted on `t3.micro` in Frankfurt (`eu-central-1`).
  * **AWS SSM Parameter Store:** API keys and database credentials are dynamically pulled directly into Docker memory at container startup, with **zero plain `.env` files written to the server disk**.

### 9. 🏗️ Terraform (Infrastructure as Code)
* **Role:** Automated AWS Provisioning.
* **Why chosen:** Provisions the EC2 instance, IAM Roles (`job-applicator-ssm-role`), security firewalls, and SSH deploy keys with a single command (`terraform apply`).

### 10. ⚡ uv + Ruff + Docker (Modern Python Tooling)
* **Role:** Package Management, Code Quality & CI/CD.
* **Why chosen:**
  * **`uv`:** 10x–100x faster dependency resolution and multi-stage Docker builds.
  * **`Ruff` & `ty`:** Enterprise-grade linting, formatting, and strict type safety.
  * **GitHub Actions:** Automated pipeline building multi-arch Docker images on GHCR and deploying via SSH.

