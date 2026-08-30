import json
import re
import asyncio
from job_applicator.clients import gemini_client
from job_applicator.config import config


async def build_queries(title: str) -> list[str]:
    """Use Gemini AI to dynamically generate targeted search queries from desired_title."""
    prompt = (
        f'Generate 3 to 5 concise job-search query strings for the role "{title}". '
        f'Return ONLY a raw JSON array of strings, e.g. ["query 1", "query 2"]. No markdown formatting or extra prose.'
    )
    
        # Run async call to Gemini API
    response = await asyncio.to_thread(
        gemini_client.models.generate_content,
        model=config.ai_model,
        contents=prompt,
    )
    
    return _parse_queries(response.text or "")

def _parse_queries(text: str) -> list[str]:
    """Extract and parse JSON array of strings from LLM text output."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return [str(q).strip() for q in data if isinstance(q, str) and q.strip()]
    except json.JSONDecodeError:
        return []