from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import dotenv
import openai
from openai.types.chat import ChatCompletionMessageParam

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
        model_name: str = "yandexgpt-lite",
        temperature: float = 0.3,
        max_tokens: int = 512,
    ):
        env = _load_env()

        self.ya_api_key = env.get("YA_API_KEY")
        self.ya_folder_id = env.get("YA_FOLDER_ID")

        if not self.ya_api_key:
            raise KeyError("Переменная YA_API_KEY не найдена в .env.")
        if not self.ya_folder_id:
            raise KeyError("Переменная YA_FOLDER_ID не найдена в .env.")

        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Файл промпта не найден: {prompt_file}")

        self.template = prompt_path.read_text(encoding="utf-8").strip()
        self.model = f"gpt://{self.ya_folder_id}/{model_name}/latest"
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = openai.OpenAI(
            api_key=self.ya_api_key,
            base_url="https://llm.api.cloud.yandex.net/v1",
        )

    def build_prompt(
        self,
        child_name: str,
        child_age: str | int,
        event_date: str,
        fact: str,
        photos_count: str | int,
    ) -> str:
        return self.template.format(
            child_name=child_name,
            child_age=child_age,
            event_date=event_date,
            fact=fact,
            photos_count=photos_count,
        )

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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.exception("Yandex LLM error")
            return f"Произошла ошибка при обращении к Yandex LLM: {e}"


_llm_service = LLMService()


def generate_post(
    child_name: str,
    child_age: str | int,
    event_date: str,
    fact: str,
    photos_count: str | int,
) -> str:
    prompt = _llm_service.build_prompt(
        child_name=child_name,
        child_age=child_age,
        event_date=event_date,
        fact=fact,
        photos_count=photos_count,
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
