"""Smoke-test OpenAI chat without printing secrets."""

from cashe.orchestrator.client import LLMClient


def main() -> None:
    client = LLMClient()
    print("provider", client.provider)
    print("model", client.models[0])
    response = client.chat(
        [{"role": "user", "content": "Reply with the single word ready"}],
        max_tokens=32,
    )
    text = response.choices[0].message.content.strip() if response.choices else ""
    print("ok", bool(text), "chars", len(text))


if __name__ == "__main__":
    main()
