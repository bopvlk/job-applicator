from sqlmodel import select

from job_applicator.storage.db import get_session
from job_applicator.storage.models import User, Job
from job_applicator.storage.dedup import filter_duplicates
from job_applicator.services.queries import build_queries
from job_applicator.services.research import search_jobs
from job_applicator.services.filter import filter_postings
from job_applicator.services.research import fetch_markdown
from job_applicator.services.analysis import analyze_job
from job_applicator.config import config

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler() -> AsyncIOScheduler:
    """Start the periodic background job search scheduler."""
    scheduler.add_job(
        run_job_search_pipeline,
        trigger="interval",
        minutes=config.run_interval_minutes,
        id="job_search_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler

async def run_job_search_pipeline() -> None:
    """Main automated job search loop executed periodically for all verified users."""
    
    # 1. Fetch all verified users from CockroachDB
    with get_session() as session:
        statement = select(User).where(User.verified == 1, User.desired_title.is_not(None))
        users = session.exec(statement).all()

    if not users:
        return

    # 2. Run pipeline per authenticated user
    for user in users:
        if not user.desired_title:
            continue
            
        # Generate targeted queries for THIS user's desired title
        queries = await build_queries(user.desired_title)
        
        # Search -> Filter -> Dedup -> Analyze
        raw_postings = await search_jobs(queries, config.target_sites)
        relevant = filter_postings(raw_postings)
        unique_postings = await filter_duplicates(relevant)
        
        for posting in unique_postings:
            if len(posting.content) < 300:
                posting.content = await fetch_markdown(posting.url)
                
        analyzed_jobs = await analyze_job(unique_postings, user.desired_title)

        # Save new analyzed jobs into CockroachDB linked to this user's email
        with get_session() as session:
            for item in analyzed_jobs:
                job_record = Job(
                    user_email=user.email,
                    uri=item.posting.url,
                    title=item.posting.title,
                    company=item.analysis.company_summary,
                    match_pct=item.analysis.match_percentage,
                    company_summary=item.analysis.company_summary,
                    red_flags=item.analysis.red_flags,
                    cover_letter=item.analysis.draft_cover_letter,
                    raw_text=item.posting.content,
                    status="New",
                )
                session.add(job_record)
            session.commit()
            
        # Send Telegram notification to user...