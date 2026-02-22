import asyncio
import types
import os

import pytest

from messengers.slack import SlackMessenger


class DummyModel:
    def __init__(self, valid=True, reason=None, image_bytes=b"pngdata"):
        self.valid = valid
        self.reason = reason
        self.image_bytes = image_bytes
        self.validate_calls = []
        self.generate_calls = []

    def validate_prompt(self, prompt):
        self.validate_calls.append(prompt)
        return (self.valid, self.reason)

    def generate_image(self, prompt, image_path):
        self.generate_calls.append((prompt, image_path))
        return self.image_bytes


class DummyRengabot:
    def __init__(self, model):
        self.model = model


class DummyClient:
    def __init__(self):
        self.uploads = []
        self.ephemeral = []
        self.views = []

    async def files_upload_v2(self, **kwargs):
        self.uploads.append(kwargs)

    async def chat_postEphemeral(self, **kwargs):
        self.ephemeral.append(kwargs)

    async def views_open(self, **kwargs):
        self.views.append(kwargs)


class DummyRespond:
    def __init__(self):
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)


class DummyAck:
    def __init__(self):
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)


def _make_slack(config, model):
    sm = SlackMessenger(config, DummyRengabot(model))
    return sm


@pytest.fixture(autouse=True)
def _disable_slack_listener_registration(monkeypatch):
    monkeypatch.setattr(SlackMessenger, "register_listeners", lambda self: None)


@pytest.mark.asyncio
async def test_slack_change_invalid_prompt(tmp_path, monkeypatch):
    config = {"bot_token": "x", "app_token": "y", "admins": []}
    model = DummyModel(valid=False, reason="too many changes")
    sm = _make_slack(config, model)

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    sm.rengabot.service.save_image_bytes("slack", "T1", "C1", b"base", ext="png")

    respond = DummyRespond()
    ack = DummyAck()
    client = DummyClient()
    body = {"user_id": "U1", "text": "change add a bird", "channel_id": "C1", "team_id": "T1"}

    await sm.handle_slash_cmd(ack, body, respond, client, types.SimpleNamespace(exception=lambda *a, **k: None))

    assert respond.calls
    assert respond.calls[0]["response_type"] == "ephemeral"


@pytest.mark.asyncio
async def test_slack_change_validation_short_circuit(tmp_path, monkeypatch):
    config = {"bot_token": "x", "app_token": "y", "admins": []}
    model = DummyModel(valid=False, reason="too many changes")
    sm = _make_slack(config, model)

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    sm.rengabot.service.save_image_bytes("slack", "T1", "C1", b"base", ext="png")

    client = DummyClient()
    await sm._handle_change_async(
        client,
        types.SimpleNamespace(exception=lambda *a, **k: None),
        "U1",
        "T1",
        "C1",
        "add a bird",
    )
    assert model.validate_calls == ["add a bird"]
    assert model.generate_calls == []
    assert client.ephemeral
    assert "Disallowed change" in client.ephemeral[0]["text"]


@pytest.mark.asyncio
async def test_slack_change_valid_prompt_uploads(tmp_path, monkeypatch):
    config = {"bot_token": "x", "app_token": "y", "admins": []}
    model = DummyModel(valid=True, image_bytes=b"newpng")
    sm = _make_slack(config, model)

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    sm.rengabot.service.save_image_bytes("slack", "T1", "C1", b"base", ext="png")

    respond = DummyRespond()
    ack = DummyAck()
    client = DummyClient()
    body = {"user_id": "U1", "text": "change add a bird", "channel_id": "C1", "team_id": "T1"}

    called = {}
    async def _run(*args, **kwargs):
        called["ok"] = True
    monkeypatch.setattr(sm, "_handle_change_async", _run)
    def _run_coro(coro):
        asyncio.get_event_loop().create_task(coro)
        return None
    monkeypatch.setattr(asyncio, "create_task", _run_coro)
    await sm.handle_slash_cmd(ack, body, respond, client, types.SimpleNamespace(exception=lambda *a, **k: None))
    await asyncio.sleep(0)
    assert called.get("ok") is True


@pytest.mark.asyncio
async def test_slack_set_image_admin_gate():
    config = {"bot_token": "x", "app_token": "y", "admins": ["U-admin"]}
    sm = _make_slack(config, DummyModel())
    respond = DummyRespond()
    ack = DummyAck()
    client = DummyClient()
    body = {"user_id": "U-not-admin", "text": "set-image", "channel_id": "C1", "team_id": "T1", "trigger_id": "TT"}

    await sm.handle_slash_cmd(ack, body, respond, client, types.SimpleNamespace(exception=lambda *a, **k: None))

    assert respond.calls
    assert "Only admins" in respond.calls[0]["text"]


def test_slack_channel_dir_and_get_current(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    config = {"bot_token": "x", "app_token": "y", "admins": []}
    sm = _make_slack(config, DummyModel())
    channel_dir = sm.rengabot.service.channel_dir("slack", "T1", "C1")
    assert channel_dir == os.path.join(str(tmp_path), "slack", "T1", "C1")
    os.makedirs(channel_dir, exist_ok=True)
    path = os.path.join(channel_dir, "current.jpeg")
    with open(path, "wb") as f:
        f.write(b"x")
    assert sm._get_current_image_path("T1", "C1") == path
