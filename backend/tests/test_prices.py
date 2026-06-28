"""Tests for the in-memory price cache and the SSE price stream."""

import asyncio
import json

from app.market.cache import PriceCache, price_cache
from app.market.stream import _price_event_generator


def test_update_and_get():
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    entry = cache.get("AAPL")
    assert entry is not None
    assert entry.price == 150.0


def test_first_update_sets_previous_price_to_current():
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    entry = cache.get("AAPL")
    assert entry.previous_price == 150.0


def test_subsequent_update_tracks_previous_price():
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    cache.update("AAPL", 155.0)
    entry = cache.get("AAPL")
    assert entry.price == 155.0
    assert entry.previous_price == 150.0


def test_get_nonexistent_returns_none():
    cache = PriceCache()
    assert cache.get("ZZZZZ") is None


def test_get_all_returns_list():
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    all_prices = cache.get_all()
    assert len(all_prices) == 1
    assert all_prices[0].ticker == "AAPL"


def test_update_stores_timestamp():
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    entry = cache.get("AAPL")
    assert entry.timestamp is not None
    assert len(entry.timestamp) > 0


async def _first_event_for(ticker):
    """Drive the SSE generator until it yields an event for `ticker`."""
    gen = _price_event_generator()
    try:
        async for event in gen:
            assert event["event"] == "price"
            payload = json.loads(event["data"])
            if payload.get("ticker") == ticker:
                return payload
    finally:
        await gen.aclose()
    return None


async def test_stream_yields_well_formed_events():
    """The SSE generator pushes well-formed price events from the shared cache."""
    # Populate the shared singleton cache the stream reads from.
    price_cache.update("AAPL", 150.0)
    price_cache.update("AAPL", 155.0)

    payload = await asyncio.wait_for(_first_event_for("AAPL"), timeout=5)

    # Each event carries ticker, price, previous price, timestamp, and direction.
    assert payload["ticker"] == "AAPL"
    assert payload["price"] == 155.0
    assert payload["previous_price"] == 150.0
    assert payload["direction"] == "up"
    assert payload["timestamp"]
