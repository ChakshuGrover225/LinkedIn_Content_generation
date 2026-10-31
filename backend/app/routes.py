import logging

import anthropic
from fastapi import APIRouter, HTTPException

from logic import settings
from logic.generate_linkedin_post import EmptyResponseError, generate_linkedin_post

from .schemas import GenerateRequest, GenerateResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


# Sync `def` on purpose: FastAPI runs it in a threadpool, so the blocking LLM calls don't stall the event loop.
@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    cfg = settings.settings.linkedin_content_generator_setting
    try:
        result = generate_linkedin_post(request.topic)
    except anthropic.APITimeoutError as e:
        logger.warning("Ollama timed out: %s", e)
        raise HTTPException(status_code=504, detail="The model timed out. Please try again.") from e
    except anthropic.APIConnectionError as e:
        logger.error("Could not reach Ollama at %s: %s", cfg.base_url, e)
        raise HTTPException(status_code=503, detail="Could not reach the Ollama server. Is it running?") from e
    except anthropic.NotFoundError as e:
        logger.error("Model %s not found on Ollama: %s", cfg.model, e)
        raise HTTPException(status_code=502, detail=f"Model '{cfg.model}' was not found on the Ollama server.") from e
    except anthropic.AuthenticationError as e:
        logger.error("Ollama rejected the API key: %s", e)
        raise HTTPException(status_code=502, detail="The Ollama server rejected the API key. Check OLLAMA_API_KEY.") from e
    except anthropic.RateLimitError as e:
        logger.warning("Ollama rate limit hit: %s", e)
        raise HTTPException(status_code=429, detail="The model is rate limiting requests. Wait a moment and try again.") from e
    except (anthropic.APIError, EmptyResponseError) as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=502, detail="The model failed to generate a post. Please try again.") from e

    return GenerateResponse(topic=request.topic, **result)
