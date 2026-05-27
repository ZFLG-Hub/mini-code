from abc import ABC, abstractmethod


class BaseBackend(ABC):
    def __init__(self, model_name, max_tokens=4096):
        self.model_name = model_name
        self.max_tokens = max_tokens

    @abstractmethod
    def chat(self, messages, stream=True):
        """Yield response chunks (str) if stream=True, else return full str."""
        ...
