import importlib
from abc import ABC, abstractmethod
from typing import Tuple

class AIModel(ABC):
    @abstractmethod
    def validate_prompt(self, prompt: str) -> Tuple[bool, str]:
        pass

    @abstractmethod
    def generate_image(prompt: str, image_path: str) -> None:
        pass
    
def load_model(class_path: str, args: dict):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls(**args)