import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Anchored to this file so prompt paths resolve the same on Windows (dev) and Linux (EC2).
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class Linkedin_content_generator_SettingClass(BaseModel):
    writer_prompt_path: Path = PROMPTS_DIR / "writer_v1.md"
    critic_prompt_path: Path = PROMPTS_DIR / "critic_v1.md"
    reviser_prompt_path: Path = PROMPTS_DIR / "reviser_v1.md"
    model: str = os.getenv("LLM_MODEL", "gpt-oss:20b-cloud")
    base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    max_tokens: int = 4000
    timeout: float = 120.0
    max_retries: int = 2


class SettingClass(BaseModel):
    # A local Ollama server ignores the key; a real one is only needed when calling ollama.com directly.
    llm_api_key: str = os.getenv("OLLAMA_API_KEY", "ollama")
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
    linkedin_content_generator_setting: Linkedin_content_generator_SettingClass = Linkedin_content_generator_SettingClass()


settings = SettingClass()
