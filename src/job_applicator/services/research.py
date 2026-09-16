import asyncio
from dataclasses import dataclass
import logging

from job_applicator.clients import get_http, tavily
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


async def search_google_serp(query: str, domains: list[str]) -> list[RawPosting] | None:
    """Tier 1: Search Google via SerpAPI with domain filters."""
    if not config.serp_api_key:
        return None

    site_filter = " OR ".join(f"site:{d.split('/')[0]}" for d in domains if d)
    full_query = f"({site_filter}) {query}" if site_filter else query

    http = get_http()
    params = {
        "engine": "google",
        "q": full_query,
        "api_key": config.serp_api_key,
        "num": "5",
        "tbs": "qdr:w",
    }

    try:
        logger.info(
            "Executing SerpAPI Google Search query",
            extra={
                "event": "serp_query_dispatched",
                "query": full_query,
                "domains": domains,
            },
        )
        async with http.get("https://serpapi.com/search.json", params=params, timeout=40) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("organic_results", [])
                postings: list[RawPosting] = []
                for r in results:
                    link = r.get("link")
                    if not link or any(pat in link.lower() for pat in IGNORE_PATTERNS):
                        continue
                    postings.append(
                        RawPosting(
                            url=link,
                            title=r.get("title", "Job Posting"),
                            content=r.get("snippet", ""),
                            score=0.9,
                        )
                    )
                return postings
            else:
                err_msg = await resp.text()
                logger.warning(
                    "SerpAPI returned non-200 status, triggering fallback to Tavily",
                    extra={
                        "event": "serp_fallback",
                        "status": resp.status,
                        "error": err_msg[:200],
                    },
                )
                return None
    except Exception as e:
        logger.warning(
            "SerpAPI call failed, falling back to Tavily",
            extra={"event": "serp_fallback", "error": str(e)},
        )
        return None


async def search_tavily(query: str, domains: list[str]) -> list[RawPosting]:
    """Tier 2: Search Tavily API."""
    try:
        logger.info(
            "Executing Tavily search query",
            extra={
                "event": "tavily_query_dispatched",
                "query": query,
                "domains": domains,
            },
        )
        data = await asyncio.to_thread(
            tavily.search,
            query=query,
            search_depth="basic",
            max_results=5,
            include_raw_content=True,
            time_range="week",
            include_domains=domains if domains else None,
        )
        results = data.get("results", [])
        postings: list[RawPosting] = []
        for r in results:
            url = r.get("url")
            if not url or any(pat in url.lower() for pat in IGNORE_PATTERNS):
                continue
            postings.append(
                RawPosting(
                    url=url,
                    title=r.get("title", ""),
                    content=r.get("raw_content") or r.get("content", ""),
                    score=float(r.get("score", 0.0)),
                )
            )
        return postings
    except Exception as e:
        err_msg = str(e)
        if "exceeds your plan's set usage limit" in err_msg or "ForbiddenError" in err_msg:
            logger.warning(
                "Tavily search skipped: monthly plan usage limit exceeded",
                extra={"event": "tavily_quota_exceeded", "query": query},
            )
        else:
            logger.error(
                "Tavily search query failed",
                exc_info=True,
                extra={"event": "tavily_query_failed", "query": query, "error": err_msg},
            )
        return []


async def search_jobs(queries: list[str], domains: list[str]) -> list[RawPosting]:
    """Search jobs using Tier 1 (SerpAPI Google Search) -> Tier 2 (Tavily) fallback."""
    postings: list[RawPosting] = []
    seen_urls: set[str] = set()
    domain_chunks = (
        [domains[i : i + CHUNK_SIZE] for i in range(0, len(domains), CHUNK_SIZE)] if domains else [[]]
    )

    for q in queries:
        for d_c in domain_chunks:
            # 1. Try SerpAPI Google Search first (Tier 1)
            batch = await search_google_serp(q, d_c)

            # 2. Fallback to Tavily (Tier 2) if SerpAPI returned None or failed
            if batch is None:
                logger.info(
                    "Falling back to Tavily for search chunk",
                    extra={"event": "search_tier_fallback", "domains": d_c},
                )
                batch = await search_tavily(q, d_c)

            for item in batch:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    postings.append(item)

    logger.info(
        "Completed search batch across all queries",
        extra={
            "event": "search_batch_completed",
            "total_queries": len(queries),
            "unique_postings_found": len(postings),
        },
    )
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