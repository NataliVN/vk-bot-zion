# app/llm_service_yandex.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
import dotenv

from app.config import settings

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

        # 🔹 ВАЖНО: Убедитесь, что в вашем .env файле переменные называются именно так:
        self.ya_api_key = env.get("YA_API_KEY")
        self.ya_folder_id = env.get("YA_FOLDER_ID")

        if not self.ya_api_key or not self.ya_folder_id:
            raise ValueError("Ошибка: YA_API_KEY и YA_FOLDER_ID обязательны в .env")

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
        messages: List[Dict[str, str]] = [
            {"role": "user", "text": prompt},
        ]

        if history:
            for msg in history:
                role = msg.get("role", "user")
                text = msg.get("text", "")
                messages.append({"role": role, "text": text})

        # 🔹 ИСПРАВЛЕННЫЙ PAYLOAD
        payload = {
            # ИСПРАВЛЕНО: правильный формат URI для YandexGPT
            "modelUri": f"gpt://{self.ya_folder_id}/yandexgpt-lite/latest",
            "completionOptions": {
                "stream": False,
                "temperature": self.temperature,
                # ИСПРАВЛЕНО: передаем как строку для надежности
                "maxTokens": str(self.max_tokens),
            },
            "messages": messages,
        }

        # 🔹 ДИАГНОСТИКА (чтобы видеть, что именно уходит)
        print("\n" + "="*50)
        print("🔍 ОТПРАВКА ЗАПРОСА К YANDEX GPT:")
        print(f"Folder ID: {self.ya_folder_id}")
        print(f"Payload: {payload}")
        print("="*50 + "\n")

        # 🔹 ИСПРАВЛЕННЫЕ HEADERS
        response = requests.post(
            url="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers={
                "Authorization": f"Api-Key {self.ya_api_key}",
                "Content-Type": "application/json",  # ДОБАВЛЕНО
                "x-folder-id": self.ya_folder_id,
            },
            json=payload,
        )

        # Если ошибка, выводим подробный текст от Яндекса
        if response.status_code != 200:
            print(f"❌ ОШИБКА YANDEX: {response.status_code}")
            print(f"Ответ сервера: {response.text}")
        
        response.raise_for_status()
        result = response.json()

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
    history.append({"role": "user", "text": prompt})
    history.append({"role": "assistant", "text": result})
    return result