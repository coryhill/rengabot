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


class ChangeInProgressError(Exception):
    pass


class GameService:
    NO_IMAGE_MESSAGE = "No image has been set yet. An admin must run `/rengabot set-image` first."
    GENERATION_ERROR_MESSAGE = "Image generation failed. Please try again."
    CHANGE_IN_PROGRESS_MESSAGE = "Someone else beat you to it"

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

    def _change_lock_path(self, platform: str, workspace_id: str, channel_id: str) -> str:
        channel_dir = self.channel_dir(platform, workspace_id, channel_id)
        return os.path.join(channel_dir, ".change.lock")

    def _acquire_change_lock(
        self, platform: str, workspace_id: str, channel_id: str
    ) -> Optional[tuple[int, str]]:
        channel_dir = self.channel_dir(platform, workspace_id, channel_id)
        os.makedirs(channel_dir, exist_ok=True)
        lock_path = self._change_lock_path(platform, workspace_id, channel_id)
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return None
        try:
            os.write(fd, str(os.getpid()).encode("ascii"))
        except Exception:
            os.close(fd)
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass
            raise
        return (fd, lock_path)

    def _release_change_lock(self, lock: Optional[tuple[int, str]]) -> None:
        if not lock:
            return
        fd, lock_path = lock
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass

    def show_image(self, platform: str, workspace_id: str, channel_id: str) -> str:
        path = self.get_current_image_path(platform, workspace_id, channel_id)
        if not path:
            raise NoImageError()
        return path

    def change_image(
        self, platform: str, workspace_id: str, channel_id: str, prompt: str
    ) -> str:
        lock = self._acquire_change_lock(platform, workspace_id, channel_id)
        if not lock:
            raise ChangeInProgressError()
        current_path = self.get_current_image_path(platform, workspace_id, channel_id)
        try:
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
        finally:
            self._release_change_lock(lock)

    @staticmethod
    def format_invalid_prompt(reason: Optional[str]) -> str:
        return f"Disallowed change: {reason or 'prompt does not match the rules.'}"
