# app/llm_service_yandex.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, cast, List, Dict, Any

import requests
import dotenv

from app.config import settings  # Для доступа кYA_API_KEY, YA_FOLDER_ID

logger = logging.getLogger(__name__)


def _load_env() -> dict:
    env_path = Path(".env")
    if not env_path.exists():
        raise FileNotFoundError("Файл .env не найден.")
    return dotenv.dotenv_values(env_path)


class YandexLLMService:
    def __init__(
        self,
        prompt_file: str = "prompts/post_prompt.txt",
        model_name: str = "yandexgpt-lite",
        temperature: float = 0.3,
        max_tokens: int = 700,
    ):
        env = _load_env()

        # 🔹 Загружаем Yandex API ключ и folder_id
        self.ya_api_key = env.get("YA_API_KEY")
        self.ya_folder_id = env.get("YA_FOLDER_ID")

        if not self.ya_api_key or not self.ya_folder_id:
            raise ValueError("Ошибка: YA_API_KEY и YA_FOLDER_ID обязательны в .env для YandexLLMService")

        # 🔹 Загружаем промпт
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Файл промпта не найден: {prompt_path}")

        self.template = prompt_path.read_text(encoding="utf-8").strip()
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

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
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        # 🔹 Формируем тело запроса для Yandex GPT API
        messages: List[Dict[str, str]] = [
            {"role": "user", "text": prompt},
        ]

        # 🔹 Добавляем историю (если есть), но YandexGPT требует "связанную" историю в одном запросе
        # Пока игнорируем, если история пуста — просто передаём одиночное сообщение
        if history:
            # У Yandex API нет прямой поддержки `history`, но мы можем "встроить" предыдущие сообщения в prompt
            for msg in history:
                role = msg.get("role", "user")
                text = msg.get("text", "")
                messages.append({"role": role, "text": text})

        # 🔹 Отправляем запрос в Yandex GPT API
        response = requests.post(
            url="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers={
                "Authorization": f"Api-Key {self.ya_api_key}",
                "x-folder-id": self.ya_folder_id,
            },
            json={
                "modelUri": f"yandex://{self.ya_folder_id}/model/{self.model_name}",
                "completionOptions": {
                    "stream": False,
                    "temperature": self.temperature,
                    "maxTokens": self.max_tokens,
                },
                "messages": messages,
            },
        )

        response.raise_for_status()
        result = response.json()

        # 🔹 Распарсиваем результат (Yandex GPT возвращает `result` в `alternatives[0].message.text`)
        alternatives = result.get("result", {}).get("alternatives", [])
        if not alternatives:
            raise ValueError("Yandex GPT вернул пустой ответ")

        content = alternatives[0].get("message", {}).get("text", "").strip()
        return content


# 🔹 Глобальный экземпляр сервиса
_yandex_llm_service = YandexLLMService()


def generate_post(
    child_name: str,
    child_age: str | int,
    event_date: str,
    fact: str,
    regen_prompt: str = "",
) -> str:
    prompt = _yandex_llm_service.build_prompt(
        child_name=child_name,
        child_age=child_age,
        event_date=event_date,
        fact=fact,
        regen_prompt=regen_prompt,
    )
    return _yandex_llm_service.chat(prompt)


def chat_with_llm(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    history = history or []
    result = _yandex_llm_service.chat(prompt, history)
    # Добавляем сообщения в историю (в формате "user"/"assistant")
    history.append({"role": "user", "text": prompt})
    history.append({"role": "assistant", "text": result})
    return result