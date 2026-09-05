"""Smoke-test OpenAI tool calling without printing secrets."""

from cashe.orchestrator.client import LLMClient


def main() -> None:
    client = LLMClient()
    print("provider", client.provider)
    print("model", client.models[0])
    tools = [
        {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "Return pong",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
    ]
    response = client.chat(
        [{"role": "user", "content": "Call ping, then stop."}],
        tools=tools,
        max_tokens=128,
    )
    message = response.choices[0].message
    print("has_tools", bool(message.tool_calls), "chars", len(message.content or ""))


if __name__ == "__main__":
    main()
