from abc import ABC, abstractmethod
from typing import Callable, Dict, Type

class ChatMessenger(ABC):
    def __init__(self, config, rengabot):
        self.config = config
        self.rengabot = rengabot
        
    @abstractmethod
    def run(self):
        pass
        
_REGISTRY: Dict[str, Type[ChatMessenger]] = {}
                
def register(name: str) -> Callable[[Type[ChatMessenger]], Type[ChatMessenger]]:
    def _decorator(cls: Type[ChatMessenger]) -> Type[ChatMessenger]:
        if not issubclass(cls, ChatMessenger):
            raise TypeError(f"{cls.__name__} must subclass ChatMessenger")
        if name in _REGISTRY:
            raise ValueError(f"Model name '{name}' already registered")
        _REGISTRY[name] = cls
        return cls
    return _decorator
                                    
def initialize_messenger(service, config, rengabot):
    if service in _REGISTRY:
        cls = _REGISTRY[service]
        instance = cls(config, rengabot)
        instance.run()
        return instance