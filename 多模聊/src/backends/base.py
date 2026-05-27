from abc import ABC, abstractmethod


class BaseBackend(ABC):
    def __init__(self, model_name):
        self.model_name = model_name

    @abstractmethod
    def chat(self, messages, stream=True):
        """Yield response chunks (str) if stream=True, else return full str."""
        ...
