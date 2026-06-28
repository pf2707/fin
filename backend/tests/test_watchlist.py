"""Tests for the watchlist API: list/add/remove, duplicates, live prices."""

import pytest

from app.market.cache import price_cache
from app.market.interface import (
    MarketDataProvider,
    set_active_provider,
    get_active_provider,
)


class FakeProvider(MarketDataProvider):
    """Records add/remove calls and seeds a price on add."""

    def __init__(self):
        self.added: list[str] = []
        self.removed: list[str] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)
        price_cache.update(ticker, 100.0)

    def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)


@pytest.fixture(autouse=True)
def seed_prices():
    """Seed the price cache and register a fake provider."""
    price_cache.update("AAPL", 190.0)
    price_cache.update("GOOGL", 175.0)
    provider = FakeProvider()
    set_active_provider(provider)
    yield provider
    set_active_provider(None)
    price_cache._prices.clear()


@pytest.mark.asyncio
async def test_list_returns_default_tickers_with_prices(client):
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    tickers = {item["ticker"] for item in data}
    # Seeded by init_db with the 10 defaults
    assert {"AAPL", "GOOGL", "MSFT", "NVDA"}.issubset(tickers)
    aapl = next(item for item in data if item["ticker"] == "AAPL")
    assert aapl["price"] == 190.0


@pytest.mark.asyncio
async def test_add_ticker_normalizes_and_tracks(client, seed_prices):
    resp = await client.post("/api/watchlist", json={"ticker": "  amd "})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AMD"
    # Provider was told to start tracking, and the price was seeded.
    assert "AMD" in seed_prices.added
    assert data["price"] == 100.0

    # It now shows up in the list.
    listing = await client.get("/api/watchlist")
    assert "AMD" in {item["ticker"] for item in listing.json()}


@pytest.mark.asyncio
async def test_add_duplicate_rejected(client):
    resp = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_empty_ticker_rejected(client):
    resp = await client.post("/api/watchlist", json={"ticker": "   "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_ticker(client):
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 200
    listing = await client.get("/api/watchlist")
    assert "AAPL" not in {item["ticker"] for item in listing.json()}


@pytest.mark.asyncio
async def test_remove_missing_ticker_404(client):
    resp = await client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
