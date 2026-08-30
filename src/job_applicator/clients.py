
import aiohttp
from google import genai
from qdrant_client import AsyncQdrantClient
from tavily import TavilyClient

from job_applicator.config import config

# Composition root for external API clients.
# Each client is built once from Config; services import the ready object
# instead of constructing their own (keeps env/config coupling in one place).
gemini_client = genai.Client(api_key=config.ai_api_key)

# Shared async HTTP session for REST calls.
# Lazy singleton so we don't build a session outside a running event loop at import.
_http: aiohttp.ClientSession | None = None

def get_http() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession()
    return _http

tavily = TavilyClient(api_key=config.tavily_api_key)

# Qdrant gets the official async client (vector upsert/search would be bug-prone by hand).
qdrant = AsyncQdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)
