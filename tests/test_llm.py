import json
from dataclasses import replace

import httpx

from app import llm
from app.config import Settings


class R:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return self

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def test_llm_disabled_without_key():
    assert llm.llm_classify(replace(Settings(), openai_api_key="", azure_openai_endpoint=""), "hi") is None


def test_llm_valid_answer(monkeypatch):
    answer = {"language": "de", "category": "charging_ev", "urgency": "normal", "confidence": 0.93}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: R(json.dumps(answer)))
    r = llm.llm_classify(replace(Settings(), openai_api_key="sk-test"), "Wallbox lädt nicht")
    assert r.category == "charging_ev" and r.engine == "openai" and r.confidence == 0.93


def test_llm_bad_answer_falls_back(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: R('{"category": "pizza"}'))
    assert llm.llm_classify(replace(Settings(), openai_api_key="sk-test"), "anything") is None
