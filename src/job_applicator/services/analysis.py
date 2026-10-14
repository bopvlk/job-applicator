import asyncio
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import TypedDict

from google.genai import types

from job_applicator.clients import gemini_client
from job_applicator.config import config
from job_applicator.services.llm import query_llm_json
from job_applicator.services.research import RawPosting
from job_applicator.storage.models import User

logger = logging.getLogger(__name__)

COVER_LETTER_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "cover_letter.md"


class UserProfileDTO(TypedDict):
    """Candidate profile parsed from PDF."""

    years_experience: int | None
    top_skills: list[str]
    key_achievements: list[str]
    preferred_location: str | None
    min_salary: str | None
    bio_summary: str | None


class CoverLetterVariants(TypedDict):
    """3 distinct tailored cover letter variations."""

    variant_1: str
    variant_2: str
    variant_3: str


class JobAnalysisResult(TypedDict):
    """Multi-factor evaluation breakdown and quality gate."""

    is_single_job_posting: bool
    is_active_and_fresh: bool
    company_summary: str
    stack_match_score: int
    seniority_match_score: int
    location_salary_match_score: int
    overall_match_score: int
    red_flags: list[str]
    fit_summary: str


@dataclass
class AnalyzedJob:
    posting: RawPosting
    analysis: JobAnalysisResult


def _build_candidate_context(user: User) -> str:
    """Format candidate profile attributes for prompt injection."""
    skills = ", ".join(user.top_skills) if user.top_skills else "Not specified"
    achievements = "\n".join(f"- {a}" for a in user.key_achievements) if user.key_achievements else "Not specified"
    return f"""
- Target Role: {user.desired_title or "Software Engineer"}
- Commercial Experience: {user.years_experience or 3}+ years
- Top Skills: {skills}
- Key Achievements:
{achievements}
- Location & Preferences: {user.preferred_location or "Remote (EU/Global)"}
- Salary Expectations: {user.min_salary or "Open / Market"}
- Professional Bio: {user.bio_summary or "Experienced engineer"}
""".strip()


async def parse_resume_pdf(pdf_bytes: bytes) -> UserProfileDTO | None:
    """Parse resume PDF bytes directly using Gemini multimodal capabilities with model fallback."""
    prompt = "Analyze this candidate's resume and extract their profile into structured JSON format."
    gemini_models = config.ai_model if isinstance(config.ai_model, list) else [config.ai_model]

    for model in gemini_models:
        try:
            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=model,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt,
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": UserProfileDTO,
                },
            )
            if response and response.text:
                data: UserProfileDTO = json.loads(response.text)
                return data
        except Exception as e:
            logger.warning(
                "Gemini model failed to parse resume PDF, trying next model",
                extra={"event": "resume_pdf_model_fallback", "model": model, "error": str(e)},
            )
            continue

    logger.error("All Gemini models failed to parse resume PDF", extra={"event": "resume_pdf_parse_error"})
    return None


async def analyze_job(posting: RawPosting, user: User) -> AnalyzedJob | None:
    """Evaluate job posting with universal LLM router against candidate profile."""
    candidate_profile = _build_candidate_context(user)
    prompt = f"""
    You are an expert technical recruiter and evaluator. Evaluate the following job posting for the candidate.

    ## Candidate Profile:
    {candidate_profile}

    ## Job Vacancy:
    - Title: {posting.title}
    - URL: {posting.url}
    - Content:
    {posting.content[:6000]}

    Evaluate if this is a single job posting, if it is active/fresh, calculate dimension scores (0-100), extract red flags, and summarize fit.
    """

    result: JobAnalysisResult | None = await query_llm_json(prompt, schema=JobAnalysisResult)
    if not result:
        return None

    return AnalyzedJob(posting=posting, analysis=result)


async def analyze_jobs(postings: list[RawPosting], user: User) -> list[AnalyzedJob]:
    """Analyze multiple job postings with concurrency throttling to prevent rate limits."""
    semaphore = asyncio.Semaphore(2)

    async def _throttled_analyze(p: RawPosting) -> AnalyzedJob | None:
        async with semaphore:
            res = await analyze_job(p, user)
            await asyncio.sleep(0.3)  # Gentle spacing between calls
            return res

    tasks = [_throttled_analyze(p) for p in postings]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def generate_cover_letters(job_title: str, job_content: str, user: User) -> CoverLetterVariants | None:
    """Generate 3 tailored cover letter variants on-demand based on custom prompt file and universal LLM router."""
    candidate_profile = _build_candidate_context(user)
    template = COVER_LETTER_PROMPT_FILE.read_text(encoding="utf-8").strip() if COVER_LETTER_PROMPT_FILE.exists() else ""

    if "{candidate_profile}" in template and "{job_description}" in template:
        prompt = template.format(
            candidate_profile=candidate_profile,
            job_description=f"Title: {job_title}\n\n{job_content[:6000]}",
        )
    else:
        prompt = f"""
        {template}

        ## Candidate Profile:
        {candidate_profile}

        ## Job Vacancy:
        Title: {job_title}
        {job_content[:6000]}
        """

    return await query_llm_json(prompt, schema=CoverLetterVariants)
