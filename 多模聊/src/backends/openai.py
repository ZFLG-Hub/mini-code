from openai import OpenAI

from .base import BaseBackend


class OpenAIBackend(BaseBackend):
    def __init__(self, model_name, api_key):
        super().__init__(model_name)
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None

    def chat(self, messages, stream=True):
        if not self.client:
            raise RuntimeError("未设置 OPENAI_API_KEY 环境变量")
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=stream,
        )
        if stream:
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        else:
            yield response.choices[0].message.content
