import asyncio
import logging
from dataclasses import dataclass

from duckduckgo_search import DDGS

from job_applicator.clients import get_http
from job_applicator.config import config

logger = logging.getLogger(__name__)

JINA_ENDPOINT = "https://r.jina.ai/"
CHUNK_SIZE = 4  # Batch domains by 4 to reduce API request volume

IGNORE_PATTERNS = [
    "/zapros/",
    "/search",
    "/category",
    "?page=",
    "query=",
    "/jobs/search",
]


@dataclass
class RawPosting:
    url: str
    title: str
    content: str
    score: float = 0.0


async def duckduckgo_search(query: str, domains: list[str]) -> list[RawPosting] | None:
    """Search DuckDuckGo with domain filters and 1-week time window."""
    site_filter = " OR ".join(f"site:{d.split('/')[0]}" for d in domains if d)
    full_query = f"({site_filter}) {query}" if site_filter else query
    logger.info(
        "Executing DuckDuckGo search query",
        extra={"event": "ddg_query_dispatched", "query": full_query, "domains": domains},
    )

    def _sync_search() -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(full_query, timelimit="d", max_results=10))

    postings: list[RawPosting] = []
    try:
        results = await asyncio.to_thread(_sync_search)
        for r in results:
            url = r.get("href")
            if not url or any(pat in url.lower() for pat in IGNORE_PATTERNS):
                continue
            postings.append(
                RawPosting(
                    url=url,
                    title=r.get("title", ""),
                    content=r.get("body", ""),
                    score=0.9,
                )
            )
    except Exception as e:
        logger.error(
            "DuckDuckGo search query failed",
            exc_info=True,
            extra={"event": "ddg_query_failed", "query": full_query, "error": str(e)},
        )
    return postings


async def search_jobs(queries: list[str], domains: list[str]) -> list[RawPosting]:
    """Search jobs using DuckDuckGo Search"""
    postings: list[RawPosting] = []
    seen_urls: set[str] = set()
    domain_chunks = [domains[i : i + CHUNK_SIZE] for i in range(0, len(domains), CHUNK_SIZE)] if domains else [[]]
    for q in queries:
        for d_c in domain_chunks:
            batch = await duckduckgo_search(q, d_c)
            for item in batch:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    postings.append(item)
    return postings


async def fetch_markdown(url: str) -> str:
    """Fetch clean markdown content for a vacancy using Jina Reader."""
    logger.info(
        "Fetching clean markdown from Jina Reader",
        extra={"event": "jina_fetch_started", "url": url},
    )
    http = get_http()
    headers = {
        "X-Return-Format": "markdown",
        "X-Engine": "direct",
    }
    if config.jina_api_key:
        headers["Authorization"] = f"Bearer {config.jina_api_key}"
    try:
        async with http.get(JINA_ENDPOINT + url, headers=headers) as resp:
            resp.raise_for_status()
            text = await resp.text()
            logger.info(
                "Successfully fetched markdown from Jina Reader",
                extra={
                    "event": "jina_fetch_success",
                    "url": url,
                    "content_length": len(text),
                },
            )
            return text
    except Exception as e:
        logger.error(
            "Failed to fetch markdown from Jina Reader",
            exc_info=True,
            extra={"event": "jina_fetch_failed", "url": url, "error": str(e)},
        )
        return ""
