from datetime import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import select

from job_applicator.bot.notifications import send_job_notification
from job_applicator.config import config
from job_applicator.enums import JobStatus
from job_applicator.services.analysis import analyze_jobs
from job_applicator.services.filter import filter_postings
from job_applicator.services.queries import build_queries
from job_applicator.services.research import fetch_markdown, search_jobs
from job_applicator.storage.db import get_session
from job_applicator.storage.dedup import filter_duplicates
from job_applicator.storage.models import Job, User

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> AsyncIOScheduler:
    """Start the periodic background job search scheduler."""
    logger.info(
        "Scheduling periodic job search pipeline",
        extra={
            "event": "scheduler_initialized",
            "interval_minutes": config.run_interval_minutes,
        },
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


async def run_pipeline_for_user(user: User) -> tuple[int, int, int]:
    """Execute search, filter, dedup, and multi-factor evaluation for a single user.

    Returns: (found_count, sent_count, discarded_count)
    """
    user_id = user.telegram_chat_id
    role = user.desired_title or "Software Engineer"

    logger.info(
        "Starting job search pipeline for user",
        extra={"event": "pipeline_started", "user_id": user_id, "role": role},
    )

    # 1. Generate search queries
    queries = await build_queries(role)
    if not queries:
        logger.warning(
            "No queries generated for role",
            extra={"event": "no_queries_generated", "user_id": user_id, "role": role},
        )
        return 0, 0, 0

    # 2. Search Tavily across target sites
    raw_postings = await search_jobs(queries, config.target_sites)
    logger.info(
        "Tavily search completed",
        extra={
            "event": "tavily_search_done",
            "user_id": user_id,
            "raw_count": len(raw_postings),
        },
    )

    if not raw_postings:
        return 0, 0, 0

    # 3. Filter relevance score threshold
    relevant = filter_postings(raw_postings)

    # 4. Qdrant Deduplication
    unique_postings = await filter_duplicates(relevant)
    logger.info(
        "Qdrant deduplication completed",
        extra={
            "event": "qdrant_dedup_done",
            "user_id": user_id,
            "unique_count": len(unique_postings),
        },
    )

    if not unique_postings:
        return len(raw_postings), 0, 0

    # 5. Fetch clean markdown from Jina Reader if needed
    for posting in unique_postings:
        if len(posting.content) < 300:
            posting.content = await fetch_markdown(posting.url)

    # 6. Analyze with Gemini (Multi-Factor TypedDict)
    analyzed_jobs = await analyze_jobs(unique_postings, user)

    sent_count = 0
    discarded_count = 0

    with get_session() as session:
        for item in analyzed_jobs:
            analysis = item.analysis

            # 🚫 Quality Gate: Skip catalog pages, stale posts, or low score
            if (
                not analysis["is_single_job_posting"]
                or not analysis["is_active_and_fresh"]
                or analysis["overall_match_score"] < user.min_match_score
            ):
                discarded_count += 1
                logger.info(
                    "Job discarded by quality gate",
                    extra={
                        "event": "job_discarded",
                        "user_id": user_id,
                        "url": item.posting.url,
                        "is_single": analysis["is_single_job_posting"],
                        "is_fresh": analysis["is_active_and_fresh"],
                        "score": analysis["overall_match_score"],
                        "min_threshold": user.min_match_score,
                    },
                )
                continue

            # 💾 Save matching job to DB
            job_record = Job(
                user_chat_id=user_id,
                uri=item.posting.url,
                title=item.posting.title,
                company=analysis.get("company_summary", "")[:100],
                match_pct=analysis["overall_match_score"],
                stack_match_pct=analysis["stack_match_score"],
                seniority_match_pct=analysis["seniority_match_score"],
                location_match_pct=analysis["location_salary_match_score"],
                company_summary=analysis.get("company_summary"),
                red_flags=", ".join(analysis.get("red_flags", [])) if analysis.get("red_flags") else None,
                raw_text=item.posting.content,
                status=JobStatus.NEW,
            )
            session.add(job_record)
            session.commit()
            session.refresh(job_record)

            # 📨 Send notification card to Telegram
            try:
                await send_job_notification(user_id, job_record)
                sent_count += 1
                logger.info(
                    "High matching job notification sent",
                    extra={
                        "event": "job_notification_sent",
                        "user_id": user_id,
                        "job_id": job_record.id,
                        "score": job_record.match_pct,
                        "url": job_record.uri,
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to send job notification to Telegram",
                    exc_info=True,
                    extra={
                        "event": "telegram_send_error",
                        "user_id": user_id,
                        "job_id": job_record.id,
                        "error": str(e),
                    },
                )

    return len(raw_postings), sent_count, discarded_count


async def run_job_search_pipeline() -> None:
    """Main automated job search loop executed periodically for all verified users."""
    logger.info("Starting automated periodic search cycle", extra={"event": "periodic_search_cycle_started"})

    with get_session() as session:
        statement = select(User).where(User.verified == 1, User.desired_title != None)  # noqa: E711
        users = session.exec(statement).all()

    if not users:
        logger.warning(
            "No verified users with desired_title found in DB. Skipping.", extra={"event": "no_active_users"}
        )
        return

    logger.info("Found active user(s) to process", extra={"event": "active_users_found", "count": len(users)})

    for user in users:
        try:
            found, sent, discarded = await run_pipeline_for_user(user)
            logger.info(
                "Completed pipeline for user",
                extra={
                    "event": "user_pipeline_completed",
                    "user_id": user.telegram_chat_id,
                    "found": found,
                    "sent": sent,
                    "discarded": discarded,
                },
            )
        except Exception as e:
            logger.error(
                "Error processing job search for user",
                exc_info=True,
                extra={"event": "user_pipeline_error", "user_id": user.telegram_chat_id, "error": str(e)},
            )

    logger.info("Completed automated periodic search cycle", extra={"event": "periodic_search_cycle_done"})
