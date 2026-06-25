from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.llm_api_key)

def chat_with_llm(prompt: str, history=None) -> str:
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()