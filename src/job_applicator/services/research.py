import asyncio
from dataclasses import dataclass

from job_applicator.clients import get_http, tavily
from job_applicator.config import config

JINA_ENDPOINT = "https://r.jina.ai/"


@dataclass
class RawPosting:
    url: str
    title: str
    content: str
    score: float = 0.0


CHUNK_SIZE = 2


IGNORE_PATTERNS = ["/zapros/", "/search", "/category", "?page=", "query=", "/jobs/search"]


async def search_jobs(queries: list[str], domains: list[str]) -> list[RawPosting]:
    postings: list[RawPosting] = []
    seen_urls: set[str] = set()
    domain_chunks = [domains[i : i + CHUNK_SIZE] for i in range(0, len(domains), CHUNK_SIZE)] or [None]

    for q in queries:
        for d_c in domain_chunks:
            data = await asyncio.to_thread(
                tavily.search,
                query=q,
                search_depth="basic",
                max_results=5,
                include_raw_content=True,
                time_range="week",
                include_domains=d_c,
            )
            for r in data.get("results", []):
                url = r["url"]

                if any(pat in url.lower() for pat in IGNORE_PATTERNS):
                    continue

                if url not in seen_urls:
                    seen_urls.add(url)
                    postings.append(
                        RawPosting(
                            url=url,
                            title=r["title"],
                            content=r["raw_content"] or r["content"],
                            score=float(r.get("score", 0.0)),
                        )
                    )
    return postings


async def fetch_markdown(url: str) -> str:
    http = get_http()
    headers = {
        "X-Return-Format": "markdown",
        "X-Engine": "direct",
    }
    if config.jina_api_key:
        headers["Authorization"] = f"Bearer {config.jina_api_key}"
    async with http.get(JINA_ENDPOINT + url, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.text()
