import json
import re

from google import genai
from job_applicator.config import load_config
from job_applicator.clients import gemini_client

config = load_config()


async def build_queries(desired_title: str) -> list[str]:
    prompt = (
        f'Generate 3 to 5 concise job-search queries for the role "{desired_title}". '
        f"Return ONLY a JSON array of strings, e.g. [\"q1\", \"q2\"]. No prose."
    )
    # точний виклик перевіримо після uv add (як робили з StateFilter)
    resp = await gemini_client.aio.models.generate_content(
        model=config.ai_model, contents=prompt
    )
    return _parse_queries(resp.text)


def _parse_queries(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [str(q).strip() for q in data if str(q).strip()]