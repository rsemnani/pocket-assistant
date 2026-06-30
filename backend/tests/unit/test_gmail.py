"""Gmail read-only provider, tested against a fake Gmail API service (no network/creds)."""

from __future__ import annotations

from pocket.core.config import Settings
from pocket.integrations.gmail import GoogleGmail


class _Exec:
    def __init__(self, value: dict) -> None:
        self._value = value

    def execute(self) -> dict:
        return self._value


class _Messages:
    def __init__(self, listing: dict, messages: dict) -> None:
        self._listing = listing
        self._messages = messages
        self.list_kwargs: dict | None = None

    def list(self, **kwargs: object) -> _Exec:
        self.list_kwargs = dict(kwargs)
        return _Exec(self._listing)

    def get(self, **kwargs: object) -> _Exec:
        return _Exec(self._messages[kwargs["id"]])


class _Users:
    def __init__(self, messages: _Messages) -> None:
        self._messages = messages

    def messages(self) -> _Messages:
        return self._messages


class _Service:
    def __init__(self, messages: _Messages) -> None:
        self._users = _Users(messages)

    def users(self) -> _Users:
        return self._users


def _service() -> tuple[_Service, _Messages]:
    listing = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    messages = {
        "m1": {
            "threadId": "t1",
            "snippet": "Wants to schedule a call.",
            "payload": {
                "headers": [
                    {"name": "From", "value": "recruiter@example.com"},
                    {"name": "Subject", "value": "Re: your application"},
                ]
            },
        },
        "m2": {
            "threadId": "t2",
            "snippet": "Following up on the invoice.",
            "payload": {"headers": [{"name": "From", "value": "billing@example.com"}]},
        },
    }
    msgs = _Messages(listing, messages)
    return _Service(msgs), msgs


def test_search_maps_results_and_builds_query():
    svc, msgs = _service()
    gmail = GoogleGmail(Settings(gmail_provider="google"), service=svc)

    out = gmail.search("follow up", window_days=2)

    assert [s.sender for s in out] == ["recruiter@example.com", "billing@example.com"]
    assert out[0].subject == "Re: your application"
    assert out[1].subject == ""  # missing Subject header tolerated
    assert out[0].gist == "Wants to schedule a call."
    # Read-only query includes the time window.
    assert "newer_than:2d" in msgs.list_kwargs["q"]
    assert msgs.list_kwargs["userId"] == "me"


def test_window_floor_is_one_day():
    svc, msgs = _service()
    gmail = GoogleGmail(Settings(gmail_provider="google"), service=svc)
    gmail.search("x", window_days=0)
    assert "newer_than:1d" in msgs.list_kwargs["q"]


def test_empty_listing_returns_empty():
    empty = _Service(_Messages({"messages": []}, {}))
    gmail = GoogleGmail(Settings(gmail_provider="google"), service=empty)
    assert gmail.search("nothing", window_days=1) == []
