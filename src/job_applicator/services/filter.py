from job_applicator.services.research import RawPosting
from job_applicator.config import load_config

config = load_config()


def filter_postings(postings: list[RawPosting]) -> list[RawPosting]:
    # Gate 1 (REAL, MVP): drop Tavily results below the configured relevance score.
    kept = [p for p in postings if p.score >= config.min_tavily_score]

    # Gate 2 (STUB): Gemini relevance judge against users.desired_description.
    # ponytail: pass-through for now so we can validate Gate 1 / Tavily scores.
    # Next step: one batched Gemini call scoring title+content vs desired_description,
    # drop where Gemini score < 0.5 (see docs/architecture.md -> Roadmap).
    return kept
