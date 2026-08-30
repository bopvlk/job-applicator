import asyncio
from pydantic import BaseModel, Field

from job_applicator.clients import gemini_client
from job_applicator.config import get_config
from job_applicator.services.research import RawPosting

config = get_config()


class JobAnalysisResult(BaseModel):
    company_summary: str = Field(description="Brief summary of the company and role")
    match_percentage: int = Field(description="Match percentage (0 to 100) based on user's target role")
    red_flags: str = Field(description="Any potential red flags or warning signs in the posting")
    draft_cover_letter: str = Field(description="Short, customized cover letter for this position")


class AnalyzedJob(BaseModel):
    posting: RawPosting
    analysis: JobAnalysisResult


async def analyze_job(posting: RawPosting, desired_title: str) -> AnalyzedJob | None:
    """Analyze a single job posting using Gemini AI structured output."""
    prompt = f"""
    Evaluate the following job posting for a candidate targeting the role: "{desired_title}".

    Job Title: {posting.title}
    Job URL: {posting.url}
    
    Job Description:
    {posting.content[:6000]}
    """

    try:
        # Request strict Pydantic JSON response from Gemini
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model=config.ai_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": JobAnalysisResult,
            },
        )
        
        # Parse Pydantic object directly from JSON
        result = JobAnalysisResult.model_validate_json(response.text)
        return AnalyzedJob(posting=posting, analysis=result)
    except Exception:
        return None


async def analyze_jobs(postings: list[RawPosting], desired_title: str) -> list[AnalyzedJob]:
    """Analyze a list of unique job postings in parallel."""
    tasks = [analyze_job(p, desired_title) for p in postings]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]