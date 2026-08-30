import asyncio
from dataclasses import dataclass

from job_applicator.clients import get_http
from job_applicator.config import load_config

config = load_config()



@dataclass
class RawPosting:
    url: str
    title: str
    content: str
    score: float = 0.0


async def search_jobs(queries: list[str]) -> list[RawPosting]:
    http = get_http()
    headers = {
        "Authorization": f"Bearer {config.tavily_api_key}",
        "Content-Type": "application/json",
    }
    postings: list[RawPosting] = []
    for q in queries:
        body = {
            "query": q,
            "search_depth": "basic",
            "max_results": 5,
            "include_raw_content": True,
            "end_date": time.time
        }
        async with http.post(TAVILY_ENDPOINT, headers=headers, json=body) as resp:
            resp.raise_for_status()
            data = await resp.json()
        for r in data.get("results", []):
            postings.append(
                RawPosting(
                    url=r["url"],
                    title=r.get("title", ""),
                    content=r.get("raw_content") or r.get("content", ""),
                    score=float(r.get("score", 0.0)),
                )
            )
    return postings


async def fetch_markdown(url: str) -> str:
    http = get_http()
    headers = {"Accept": "text/markdown"}
    if config.jina_api_key:
        headers["Authorization"] = f"Bearer {config.jina_api_key}"
    async with http.get(JINA_ENDPOINT + url, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.text()
