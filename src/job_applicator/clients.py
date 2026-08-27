from google import genai

from job_applicator.config import load_config

config = load_config()

# Composition root for external API clients.
# Each client is built once from Config; services import the ready object
# instead of constructing their own (keeps env/config coupling in one place).
gemini_client = genai.Client(api_key=config.ai_api_key)

# Add Tavily, Jina Reader, Qdrant Cloud clients here as they are built.
