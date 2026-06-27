from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

import dotenv

logger = logging.getLogger(__name__)


def _load_env() -> dict:
    env_path = Path(".env")
    if not env_path.exists():
        raise FileNotFoundError("Файл .env не найден.")
    return dotenv.dotenv_values(env_path)


class LLMService:
    def __init__(
        self,
        prompt_file: str = "prompts/post_prompt.txt",
        model_name: str = "gemma3:1b",
        temperature: float = 0.3,
        max_tokens: int = 700,
    ):
        env = _load_env()
        self.ollama_base_url = env.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model_name = env.get("OLLAMA_MODEL", model_name)

        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Файл промпта не найден: {prompt_file}")

        self.template = prompt_path.read_text(encoding="utf-8").strip()
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(
            base_url=self.ollama_base_url,
            api_key="ollama",
        )

    def build_prompt(
        self,
        child_name: str,
        child_age: str | int,
        event_date: str,
        fact: str,
        regen_prompt: str = "",
    ) -> str:
        base = self.template.format(
            child_name=child_name,
            child_age=child_age,
            event_date=event_date,
            fact=fact,
        )
        if regen_prompt:
            base += f"\n\nУточнение от оператора: {regen_prompt}"
        return base

    def chat(
        self,
        prompt: str,
        history: list[ChatCompletionMessageParam] | None = None,
    ) -> str:
        history = history or []
        messages: list[ChatCompletionMessageParam] = [
            {"role": "user", "content": prompt},
            *history,
        ]
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return (response.choices[0].message.content or "").strip()


_llm_service = LLMService()


def generate_post(
    child_name: str,
    child_age: str | int,
    event_date: str,
    fact: str,
    regen_prompt: str = "",
) -> str:
    prompt = _llm_service.build_prompt(
        child_name=child_name,
        child_age=child_age,
        event_date=event_date,
        fact=fact,
        regen_prompt=regen_prompt,
    )
    return _llm_service.chat(prompt)


def chat_with_llm(
    prompt: str,
    history: list[ChatCompletionMessageParam] | None = None,
) -> str:
    history = history or []
    result = _llm_service.chat(prompt, history)
    history.append(cast(ChatCompletionMessageParam, {"role": "user", "content": prompt}))
    history.append(cast(ChatCompletionMessageParam, {"role": "assistant", "content": result}))
    return result
