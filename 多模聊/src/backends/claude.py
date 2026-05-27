from anthropic import Anthropic

from .base import BaseBackend


class ClaudeBackend(BaseBackend):
    def __init__(self, model_name, api_key):
        super().__init__(model_name)
        self.api_key = api_key
        self.client = Anthropic(api_key=api_key) if api_key else None

    def chat(self, messages, stream=True):
        if not self.client:
            raise RuntimeError("未设置 ANTHROPIC_API_KEY 环境变量")
        system_prompt = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs = dict(
            model=self.model_name,
            messages=chat_messages,
            max_tokens=8192,
            stream=stream,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        with self.client.messages.stream(**kwargs) as stream_ctx:
            for text in stream_ctx.text_stream:
                yield text
