import logging

from job_applicator.services.llm import query_llm_json

logger = logging.getLogger(__name__)


async def build_queries(title: str) -> list[str]:
    """Dynamically generate targeted search queries from desired_title using universal LLM router."""
    prompt = (
        f'Generate 3 to 5 concise job-search query strings for the role "{title}". '
        f'Return a JSON array of query strings, e.g. ["query 1", "query 2"].'
    )

    result = await query_llm_json(prompt, schema=list[str])

    if isinstance(result, list):
        return [str(q).strip() for q in result if isinstance(q, str) and q.strip()]

    # Fallback if wrapped in a dictionary (e.g. {"queries": [...]})
    if isinstance(result, dict):
        for val in result.values():
            if isinstance(val, list):
                return [str(q).strip() for q in val if isinstance(q, str) and q.strip()]

    logger.warning("Failed to generate queries from LLM", extra={"event": "query_gen_failed", "title": title})
    return []
