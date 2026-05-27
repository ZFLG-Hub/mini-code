from google import genai

from .base import BaseBackend


class GeminiBackend(BaseBackend):
    def __init__(self, model_name, api_key):
        super().__init__(model_name)
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key) if api_key else None

    def chat(self, messages, stream=True):
        if not self.client:
            raise RuntimeError("未设置 GEMINI_API_KEY 环境变量")
        contents = self._convert_messages(messages)

        response = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

    def _convert_messages(self, messages):
        contents = []
        system_parts = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        if system_parts:
            system_text = "\n".join(system_parts)
            if contents and contents[0]["role"] == "user":
                contents[0]["parts"].insert(0, {"text": f"[System]\n{system_text}\n\n"})
            else:
                contents.insert(0, {"role": "user", "parts": [{"text": f"[System]\n{system_text}"}]})

        return contents
