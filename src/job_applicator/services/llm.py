import asyncio
import json
import logging
from typing import Any

from job_applicator.clients import gemini_client, get_http
from job_applicator.config import config

logger = logging.getLogger(__name__)


async def query_llm_json(
    prompt: str,
    schema: type | None = None,
) -> Any | None:
    """Universal LLM caller with multi-model and multi-provider fallback.

    Execution chain: 1. Gemini models list (config.ai_model) 2. Mistral models
    list (config.mistral_model)
    """

    # ─── 1. TIER: Google Gemini Models ──────────────────────────────
    gemini_models = config.ai_model if isinstance(config.ai_model, list) else [config.ai_model]
    for model in gemini_models:
        try:
            gen_config: dict[str, Any] = {"response_mime_type": "application/json"}
            if schema is not None:
                gen_config["response_schema"] = schema

            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=model,
                contents=prompt,
                config=gen_config,
            )
            if response and response.text:
                text = response.text.strip()
                if text.startswith("```"):
                    lines = text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text = "\n".join(lines).strip()
                return json.loads(text)
        except Exception as e:
            logger.warning(
                "Gemini model attempt failed, falling back",
                extra={
                    "event": "llm_model_fallback",
                    "provider": "gemini",
                    "model": model,
                    "error": str(e),
                },
            )
            continue

    # ─── 2. TIER: Mistral AI Models ─────────────────────────────────
    if config.mistral_api_key:
        mistral_models = config.mistral_model if isinstance(config.mistral_model, list) else [config.mistral_model]
        http = get_http()
        endpoint = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.mistral_api_key}",
            "Content-Type": "application/json",
        }

        keys_hint = ""
        if schema is not None and hasattr(schema, "__annotations__"):
            keys = list(schema.__annotations__.keys())
            keys_hint = f"\nThe JSON object MUST contain the following fields: {keys}."

        mistral_prompt = f"{prompt}\n\nIMPORTANT: Respond with STRICT valid JSON only.{keys_hint}"

        for model in mistral_models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": mistral_prompt}],
                    "response_format": {"type": "json_object"},
                }
                async with http.post(endpoint, headers=headers, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        if content.startswith("```"):
                            lines = content.splitlines()
                            if lines[0].startswith("```"):
                                lines = lines[1:]
                            if lines and lines[-1].startswith("```"):
                                lines = lines[:-1]
                            content = "\n".join(lines).strip()
                        return json.loads(content)
                    else:
                        err_text = await resp.text()
                        logger.warning(
                            "Mistral API attempt returned error",
                            extra={
                                "event": "llm_model_fallback",
                                "provider": "mistral",
                                "model": model,
                                "status_code": resp.status,
                                "error": err_text[:200],
                            },
                        )
                        continue
            except Exception as e:
                logger.warning(
                    "Mistral call exception, trying next",
                    extra={
                        "event": "llm_model_fallback",
                        "provider": "mistral",
                        "model": model,
                        "error": str(e),
                    },
                )
                continue

    logger.error(
        "All LLM models and providers exhausted",
        extra={"event": "llm_all_providers_failed"},
    )
    return None

