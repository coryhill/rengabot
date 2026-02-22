import json
import types

from model.gemini import GeminiModel


class DummyClient:
    def __init__(self, response):
        self._response = response
        self.models = types.SimpleNamespace(generate_content=self._generate_content, list=self._list)

    def _generate_content(self, **kwargs):
        return self._response

    def _list(self):
        return []


def test_validate_prompt_parses_json(monkeypatch):
    response = types.SimpleNamespace(text=json.dumps({"valid": True}))
    model = GeminiModel(api_key="x")
    model.client = DummyClient(response)

    valid, reason = model.validate_prompt("add a bird")
    assert valid is True
    assert reason is None


def test_validate_prompt_handles_bad_json(monkeypatch):
    response = types.SimpleNamespace(text="not json")
    model = GeminiModel(api_key="x")
    model.client = DummyClient(response)

    valid, reason = model.validate_prompt("add a bird")
    assert valid is False
    assert reason == "AI model returned a bad response"


def test_generate_image_extracts_bytes(monkeypatch, tmp_path):
    part = types.SimpleNamespace(inline_data=types.SimpleNamespace(data=b"img"))
    response = types.SimpleNamespace(parts=[part])
    model = GeminiModel(api_key="x")
    model.client = DummyClient(response)

    path = tmp_path / "current.png"
    path.write_bytes(b"base")
    data = model.generate_image("add a bird", str(path))
    assert data == b"img"
