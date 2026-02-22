import os
from typing import Optional


class NoImageError(Exception):
    pass


class InvalidPromptError(Exception):
    def __init__(self, reason: Optional[str] = None):
        super().__init__(reason or "prompt does not match the rules")
        self.reason = reason


class GenerationError(Exception):
    pass


class GameService:
    NO_IMAGE_MESSAGE = "No image has been set yet. An admin must run `/rengabot set-image` first."
    GENERATION_ERROR_MESSAGE = "Image generation failed. Please try again."

    def __init__(self, model, uploads_dir: Optional[str] = None):
        self.model = model
        self.uploads_dir = uploads_dir or os.environ.get("UPLOADS_DIR", "/tmp")

    def channel_dir(self, platform: str, workspace_id: str, channel_id: str) -> str:
        return os.path.join(self.uploads_dir, platform, workspace_id, channel_id)

    def get_current_image_path(
        self, platform: str, workspace_id: str, channel_id: str
    ) -> Optional[str]:
        channel_dir = self.channel_dir(platform, workspace_id, channel_id)
        for ext in ("png", "jpg", "jpeg"):
            path = os.path.join(channel_dir, f"current.{ext}")
            if os.path.exists(path):
                return path
        return None

    def save_image_bytes(
        self,
        platform: str,
        workspace_id: str,
        channel_id: str,
        image_bytes: bytes,
        ext: str = "png",
    ) -> str:
        if ext not in ("png", "jpg", "jpeg"):
            ext = "png"
        channel_dir = self.channel_dir(platform, workspace_id, channel_id)
        os.makedirs(channel_dir, exist_ok=True)
        path = os.path.join(channel_dir, f"current.{ext}")
        with open(path, "wb") as f:
            f.write(image_bytes)
        return path

    def save_image_file(
        self,
        platform: str,
        workspace_id: str,
        channel_id: str,
        src_path: str,
        ext: str = "png",
    ) -> str:
        if ext not in ("png", "jpg", "jpeg"):
            ext = "png"
        channel_dir = self.channel_dir(platform, workspace_id, channel_id)
        os.makedirs(channel_dir, exist_ok=True)
        dest_path = os.path.join(channel_dir, f"current.{ext}")
        os.replace(src_path, dest_path)
        return dest_path

    def show_image(self, platform: str, workspace_id: str, channel_id: str) -> str:
        path = self.get_current_image_path(platform, workspace_id, channel_id)
        if not path:
            raise NoImageError()
        return path

    def change_image(
        self, platform: str, workspace_id: str, channel_id: str, prompt: str
    ) -> str:
        current_path = self.get_current_image_path(platform, workspace_id, channel_id)
        if not current_path:
            raise NoImageError()
        valid, reason = self.model.validate_prompt(prompt)
        if not valid:
            raise InvalidPromptError(reason)
        try:
            image_bytes = self.model.generate_image(prompt, current_path)
        except Exception as e:
            raise GenerationError(str(e)) from e
        return self.save_image_bytes(
            platform, workspace_id, channel_id, image_bytes, ext="png"
        )

    @staticmethod
    def format_invalid_prompt(reason: Optional[str]) -> str:
        return f"Disallowed change: {reason or 'prompt does not match the rules.'}"
