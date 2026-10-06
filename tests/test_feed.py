"""Regression tests for Display Canvas feed URL helpers."""

from types import SimpleNamespace

import custom_components.display_canvas.feed as feed
from custom_components.display_canvas.const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE_URL,
)


def _entry(
    *,
    options: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        options=options or {},
        data={CONF_ACCESS_TOKEN: "test-token"},
    )


def test_configured_base_url() -> None:
    """Configured Base URL takes precedence."""
    entry = _entry(
        options={
            CONF_BASE_URL: "http://192.168.1.230:8123/",
        }
    )

    assert (
        feed.feed_base_url(None, entry)
        == "http://192.168.1.230:8123"
    )


def test_feed_url() -> None:
    """Feed URL includes base URL, token, and filename."""
    entry = _entry(
        options={
            CONF_BASE_URL: "http://192.168.1.230:8123/",
        }
    )

    assert feed.feed_url(
        None,
        entry,
        "aerial.csv",
    ) == (
        "http://192.168.1.230:8123/"
        "api/display_canvas/test-token/aerial.csv"
    )


def test_home_assistant_local_url(monkeypatch) -> None:
    """Home Assistant local URL is used when no Base URL is set."""
    called = {}

    def fake_get_url(hass, **kwargs):
        called.update(kwargs)
        return "http://homeassistant.local:8123"

    monkeypatch.setattr(feed, "get_url", fake_get_url)

    assert (
        feed.feed_base_url(None, _entry())
        == "http://homeassistant.local:8123"
    )

    assert called == {
        "allow_internal": True,
        "allow_external": False,
        "allow_cloud": False,
        "prefer_external": False,
    }
