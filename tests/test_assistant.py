from botocore.exceptions import ClientError

from core import assistant


class FakeBedrock:
    def __init__(self, refuse):
        self.refuse, self.models = refuse, []

    def converse(self, **kw):
        self.models.append(kw["modelId"])
        if kw["modelId"] in self.refuse:
            raise ClientError({"Error": {"Code": self.refuse[kw["modelId"]], "Message": "no"}}, "Converse")
        return {"output": {"message": {"content": [{"text": "hello"}]}}, "stopReason": "end_turn", "usage": {}}


def use(monkeypatch, refuse):
    fake = FakeBedrock(refuse)
    monkeypatch.setattr(assistant, "_client", fake)
    monkeypatch.setattr(assistant, "MODEL_ID", "primary")
    monkeypatch.setattr(assistant, "MODEL_FALLBACK_ID", "backup")
    return fake


def test_primary_model_used_when_available(monkeypatch):
    fake = use(monkeypatch, {})
    assert assistant.chat("hi") == {"text": "hello", "source": "bedrock", "model": "primary"}
    assert fake.models == ["primary"]


def test_refused_model_falls_back_to_second_model(monkeypatch):
    fake = use(monkeypatch, {"primary": "AccessDeniedException"})
    assert assistant.chat("hi")["model"] == "backup"
    assert fake.models == ["primary", "backup"]


def test_outage_uses_rules_text_without_trying_second_model(monkeypatch):
    fake = use(monkeypatch, {"primary": "ServiceUnavailableException"})
    out = assistant.chat("hi")
    assert out["source"] == "fallback" and "10111" in out["text"]
    assert fake.models == ["primary"]
