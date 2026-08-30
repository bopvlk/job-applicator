import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import select

from job_applicator.bot.notifications import send_job_notification
from job_applicator.config import config
from job_applicator.services.analysis import analyze_jobs
from job_applicator.services.filter import filter_postings
from job_applicator.services.queries import build_queries
from job_applicator.services.research import fetch_markdown, search_jobs
from job_applicator.storage.db import get_session
from job_applicator.storage.dedup import filter_duplicates
from job_applicator.storage.models import Job, User

logger = logging.getLogger("job_applicator.scheduler")

scheduler = AsyncIOScheduler()


def start_scheduler() -> AsyncIOScheduler:
    """Start the periodic background job search scheduler."""
    logger.info(
        "Scheduling job search pipeline: interval=%d min, next_run=NOW",
        config.run_interval_minutes,
    )
    scheduler.add_job(
        run_job_search_pipeline,
        trigger="interval",
        minutes=config.run_interval_minutes,
        next_run_time=datetime.now(),
        id="job_search_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


async def run_job_search_pipeline() -> None:
    """Main automated job search loop executed periodically for all verified users."""
    logger.info("🔍 [Pipeline] Starting automated job search cycle...")

    # 1. Fetch all verified users from CockroachDB
    with get_session() as session:
        statement = select(User).where(User.verified == 1, User.desired_title.is_not(None))
        users = session.exec(statement).all()

    if not users:
        logger.warning("⚠️ [Pipeline] No verified users with desired_title found in DB. Skipping.")
        return

    logger.info("👥 [Pipeline] Found %d verified user(s) to process", len(users))

    # 2. Run pipeline per authenticated user
    for user in users:
        if not user.desired_title:
            continue

        logger.info(
            "👤 Processing user [chat_id=%s, email=%s, target_role='%s']",
            user.telegram_chat_id,
            user.email,
            user.desired_title,
        )

        try:
            # Generate targeted queries for THIS user's desired title
            logger.info("🤖 Generating search queries via Gemini...")
            queries = await build_queries(user.desired_title)
            logger.info("🔎 Generated %d query strings: %s", len(queries), queries)

            if not queries:
                logger.warning("No search queries generated for role '%s'. Skipping.", user.desired_title)
                continue

            # Search -> Filter -> Dedup -> Analyze
            logger.info("🌐 Searching Tavily across target sites: %s", config.target_sites)
            raw_postings = await search_jobs(queries, config.target_sites)
            logger.info("📥 Found %d raw postings from Tavily", len(raw_postings))

            relevant = filter_postings(raw_postings)
            logger.info("🎯 Filtered to %d relevant postings (score >= %.2f)", len(relevant), config.min_tavily_score)

            unique_postings = await filter_duplicates(relevant)
            logger.info("✨ %d unique postings after Qdrant deduplication", len(unique_postings))

            if not unique_postings:
                logger.info("No new unique jobs to analyze for %s", user.email)
                continue

            # Fetch full Markdown if needed
            for posting in unique_postings:
                if len(posting.content) < 300:
                    logger.debug("Fetching clean markdown from Jina for: %s", posting.url)
                    posting.content = await fetch_markdown(posting.url)

            # Analyze jobs with Gemini
            logger.info("🧠 Analyzing %d jobs with Gemini AI...", len(unique_postings))
            analyzed_jobs = await analyze_jobs(unique_postings, user.desired_title)
            logger.info("📊 Successfully analyzed %d jobs", len(analyzed_jobs))

            # Save new analyzed jobs into CockroachDB linked to this user
            created_jobs: list[Job] = []
            with get_session() as session:
                for item in analyzed_jobs:
                    job_record = Job(
                        user_chat_id=user.telegram_chat_id,
                        uri=item.posting.url,
                        title=item.posting.title,
                        company=item.analysis.company_summary[:100] if item.analysis.company_summary else None,
                        match_pct=item.analysis.match_percentage,
                        company_summary=item.analysis.company_summary,
                        red_flags=item.analysis.red_flags,
                        cover_letter=item.analysis.draft_cover_letter,
                        raw_text=item.posting.content,
                        status="New",
                    )
                    session.add(job_record)
                    created_jobs.append(job_record)
                session.commit()
                # Refresh IDs
                for job in created_jobs:
                    session.refresh(job)

            logger.info("💾 Saved %d new jobs to CockroachDB", len(created_jobs))

            # Send Telegram notification for each analyzed job
            if user.telegram_chat_id:
                logger.info(
                    "📤 Sending %d Telegram job notification(s) to chat_id=%s",
                    len(created_jobs),
                    user.telegram_chat_id,
                )
                for job_record in created_jobs:
                    try:
                        await send_job_notification(user.telegram_chat_id, job_record)
                    except Exception as e:
                        logger.error("Failed to send Telegram notification for job %s: %s", job_record.id, e)

        except Exception as e:
            logger.exception("❌ Error processing job search for user %s: %s", user.email, e)

    logger.info("🏁 [Pipeline] Completed automated job search cycle.")
