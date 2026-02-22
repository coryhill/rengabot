import os

import pytest

from game.service import (
    ChangeInProgressError,
    GameService,
    InvalidPromptError,
    NoImageError,
)


class DummyModel:
    def __init__(self, valid=True, reason=None, image_bytes=b"img"):
        self.valid = valid
        self.reason = reason
        self.image_bytes = image_bytes

    def validate_prompt(self, prompt):
        return (self.valid, self.reason)

    def generate_image(self, prompt, image_path):
        return self.image_bytes


def test_show_image_no_image(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    svc = GameService(DummyModel())
    with pytest.raises(NoImageError):
        svc.show_image("slack", "T1", "C1")


def test_change_image_invalid_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    svc = GameService(DummyModel(valid=False, reason="too many changes"))
    svc.save_image_bytes("slack", "T1", "C1", "U1", b"base")
    with pytest.raises(InvalidPromptError) as exc:
        svc.change_image("slack", "T1", "C1", "U2", "add a bird")
    assert "too many changes" in str(exc.value)


def test_change_image_saves_new_image(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    svc = GameService(DummyModel(valid=True, image_bytes=b"new"))
    svc.save_image_bytes("slack", "T1", "C1", "U1", b"base")
    path = svc.change_image("slack", "T1", "C1", "U2", "add a bird")
    assert os.path.exists(path)
    assert open(path, "rb").read() == b"new"


def test_change_image_fails_when_locked(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    svc = GameService(DummyModel(valid=True, image_bytes=b"new"))
    svc.save_image_bytes("slack", "T1", "C1", "U1", b"base")
    lock_path = svc._change_lock_path("slack", "T1", "C1")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "w") as lock_file:
        lock_file.write("locked")
    with pytest.raises(ChangeInProgressError):
        svc.change_image("slack", "T1", "C1", "U2", "add a bird")
