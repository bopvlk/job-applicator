import asyncio
from dataclasses import dataclass
import logging

from job_applicator.clients import get_http, tavily
from job_applicator.config import config

logger = logging.getLogger(__name__)

JINA_ENDPOINT = "https://r.jina.ai/"


@dataclass
class RawPosting:
    url: str
    title: str
    content: str
    score: float = 0.0


CHUNK_SIZE = 4


IGNORE_PATTERNS = ["/zapros/", "/search", "/category", "?page=", "query=", "/jobs/search"]


async def search_jobs(queries: list[str], domains: list[str]) -> list[RawPosting]:
    postings: list[RawPosting] = []
    seen_urls: set[str] = set()
    domain_chunks: list[list[str]] = (
        [domains[i : i + CHUNK_SIZE] for i in range(0, len(domains), CHUNK_SIZE)] if domains else [[]]
    )

    for q in queries:
        for d_c in domain_chunks:
            logger.info(
                "Executing Tavily search query",
                extra={
                    "event": "tavily_query_dispatched",
                    "query": q,
                    "domains": d_c,
                },
            )
            try:
                if d_c:
                    data = await asyncio.to_thread(
                        tavily.search,
                        query=q,
                        search_depth="basic",
                        max_results=5,
                        include_raw_content=True,
                        time_range="week",
                        include_domains=d_c,
                    )
                else:
                    data = await asyncio.to_thread(
                        tavily.search,
                        query=q,
                        search_depth="basic",
                        max_results=5,
                        include_raw_content=True,
                        time_range="week",
                    )
            except Exception as e:
                logger.error(
                    "Tavily search query failed",
                    exc_info=True,
                    extra={
                        "event": "tavily_query_failed",
                        "query": q,
                        "domains": d_c,
                        "error": str(e),
                    },
                )
                continue

            results = data.get("results", [])
            logger.info(
                "Tavily query returned results",
                extra={
                    "event": "tavily_query_returned",
                    "query": q,
                    "result_count": len(results),
                },
            )

            for r in results:
                url = r["url"]

                if any(pat in url.lower() for pat in IGNORE_PATTERNS):
                    logger.debug(
                        "Ignored catalog or search result URL",
                        extra={"event": "catalog_url_ignored", "url": url},
                    )
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
