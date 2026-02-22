import os
import types

import pytest

from messengers.discord import DiscordMessenger
from game.service import GameService


class DummyModel:
    def __init__(self, valid=True, reason=None, image_bytes=b"pngdata"):
        self.valid = valid
        self.reason = reason
        self.image_bytes = image_bytes

    def validate_prompt(self, prompt):
        return (self.valid, self.reason)

    def generate_image(self, prompt, image_path):
        return self.image_bytes


class DummyRengabot:
    def __init__(self, model):
        self.model = model
        self.service = GameService(model)


def _make_discord(tmp_path):
    config = {"bot_token": "x", "guild_id": "1", "admins": ["1"]}
    dm = DiscordMessenger(config, DummyRengabot(DummyModel()))
    return dm


def test_discord_channel_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    dm = _make_discord(tmp_path)
    path = dm._channel_dir("g", "c")
    assert path == os.path.join(str(tmp_path), "discord", "g", "c")


def test_discord_get_current_image_path(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    dm = _make_discord(tmp_path)
    channel_dir = dm._channel_dir("g", "c")
    os.makedirs(channel_dir, exist_ok=True)
    img = os.path.join(channel_dir, "current.jpg")
    with open(img, "wb") as f:
        f.write(b"x")
    assert dm._get_current_image_path("g", "c") == img


def test_discord_admin_gate(tmp_path):
    dm = _make_discord(tmp_path)
    user = types.SimpleNamespace(id=2)
    assert dm._is_admin(user) is False
