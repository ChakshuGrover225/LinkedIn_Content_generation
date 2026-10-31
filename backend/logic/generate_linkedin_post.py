import logging
from pathlib import Path

import anthropic

from . import settings

logger = logging.getLogger(__name__)

DEFAULT_WRITER_PROMPT = "You are a LinkedIn post writer. Write under 200 words."
DEFAULT_CRITIC_PROMPT = "You are a critic. Give exactly 5 numbered suggestions to improve the draft. Do not rewrite it."
DEFAULT_REVISER_PROMPT = "You are an editor. Rewrite the draft to address the critique. Output only the revised post."


class EmptyResponseError(RuntimeError):
    """The LLM returned no text content."""


def read_prompt(file_path: Path) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Prompt file not found: %s, using default prompt", file_path)
        return ""


class Agent:
    """Minimal agent: a name, a system prompt, a way to produce a response."""

    def __init__(self, name: str, client: anthropic.Anthropic, model: str, system_prompt: str, max_tokens: int):
        self.name = name
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens

    def run(self, input_text: str) -> str:
        logger.info("Running %s agent", self.name)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": input_text}],
        )
        content = "".join(b.text for b in response.content if b.type == "text").strip()
        if not content:
            raise EmptyResponseError(f"The {self.name} agent returned an empty response.")
        return content


def build_client() -> anthropic.Anthropic:
    cfg = settings.settings.linkedin_content_generator_setting
    return anthropic.Anthropic(
        base_url=cfg.base_url,
        api_key=settings.settings.llm_api_key,
        timeout=cfg.timeout,
        max_retries=cfg.max_retries,
    )


def build_agents(client: anthropic.Anthropic) -> tuple[Agent, Agent, Agent]:
    """3 subagents: writer, critic, reviser — configured from settings.py."""
    cfg = settings.settings.linkedin_content_generator_setting

    def make(name: str, prompt_path: Path, default_prompt: str) -> Agent:
        return Agent(
            name=name,
            client=client,
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            system_prompt=read_prompt(prompt_path) or default_prompt,
        )

    return (
        make("writer", cfg.writer_prompt_path, DEFAULT_WRITER_PROMPT),
        make("critic", cfg.critic_prompt_path, DEFAULT_CRITIC_PROMPT),
        make("reviser", cfg.reviser_prompt_path, DEFAULT_REVISER_PROMPT),
    )


def run_chain(writer: Agent, critic: Agent, reviser: Agent, topic: str) -> dict:
    draft = writer.run(f"Write a LinkedIn post about: {topic}")
    critique = critic.run(f"Draft:\n{draft}\n\nTopic: {topic}")
    revised = reviser.run(f"Draft:\n{draft}\n\nCritique:\n{critique}")
    return {"draft": draft, "critique": critique, "revised": revised}


def generate_linkedin_post(topic: str) -> dict:
    """Orchestrator: builds the client and agents from settings.py and runs the
    writer -> critic -> reviser chain in one call. Single entry point for the API."""
    with build_client() as client:
        writer, critic, reviser = build_agents(client)
        return run_chain(writer, critic, reviser, topic)


# Run from backend/ as a module (relative imports need the package): python -m logic.generate_linkedin_post "topic"
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    topic = " ".join(sys.argv[1:]) or "Lessons from building a multi-agent LinkedIn post generator"
    result = generate_linkedin_post(topic)
    for section in ("draft", "critique", "revised"):
        print(f"\n===== {section.upper()} =====\n{result[section]}")
