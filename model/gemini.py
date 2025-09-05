import os
from typing import Tuple
from google import genai
from .base import AIModel

DEFAULT_INTENT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image-preview"

class GeminiModel(AIModel):
    def __init__(self, api_key=None, intent_model=DEFAULT_INTENT_MODEL, image_model=DEFAULT_IMAGE_MODEL):
        if os.environ.get("GEMINI_API_KEY"):
            self.api_key = os.environ["GEMINI_API_KEY"]
        elif api_key:
            self.api_key = api_key
        else:
            raise Exception("no API key set for Gemini")
        self.intent_model = intent_model
        self.image_model = image_model
        
    def validate_prompt(self, prompt: str) -> Tuple[bool, str]:
        pass

    def generate_image(self, prompt: str):
        pass