"""Tests for the GBM market data simulator and market data providers."""

import inspect

import numpy as np

from app.market.cache import PriceCache
from app.market.interface import MarketDataProvider
from app.market.massive import MassiveClient
from app.market.provider import create_provider
from app.market.simulator import (
    TICKER_CONFIG,
    _build_correlation_matrix,
    Simulator,
)


def test_ticker_config_has_required_fields():
    for ticker, cfg in TICKER_CONFIG.items():
        assert "seed" in cfg, f"{ticker} missing seed"
        assert "drift" in cfg, f"{ticker} missing drift"
        assert "vol" in cfg, f"{ticker} missing vol"
        assert cfg["seed"] > 0, f"{ticker} seed must be positive"
        assert cfg["vol"] > 0, f"{ticker} volatility must be positive"


def test_correlation_matrix_is_symmetric():
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    np.testing.assert_array_almost_equal(corr, corr.T)


def test_correlation_matrix_has_ones_on_diagonal():
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    np.testing.assert_array_almost_equal(np.diag(corr), np.ones(len(tickers)))


def test_correlation_matrix_tech_cluster():
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    # Find two tech tickers
    i = tickers.index("AAPL")
    j = tickers.index("GOOGL")
    assert corr[i, j] == 0.6


def test_correlation_matrix_finance_cluster():
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    i = tickers.index("JPM")
    j = tickers.index("V")
    assert corr[i, j] == 0.5


def test_correlation_matrix_cross_sector():
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    i = tickers.index("AAPL")
    j = tickers.index("JPM")
    assert corr[i, j] == 0.2


def test_correlation_matrix_is_positive_definite():
    """A valid correlation matrix must be positive definite for Cholesky."""
    tickers = list(TICKER_CONFIG.keys())
    corr = _build_correlation_matrix(tickers)
    # Cholesky will raise if not positive definite
    np.linalg.cholesky(corr)


def test_simulator_initializes_with_seed_prices():
    sim = Simulator()
    for ticker, cfg in TICKER_CONFIG.items():
        assert sim._prices[ticker] == cfg["seed"]


def test_simulator_step_produces_valid_prices():
    sim = Simulator()
    sim._step()
    for ticker in TICKER_CONFIG:
        assert sim._prices[ticker] >= 0.01, f"{ticker} price below floor"


def test_simulator_step_changes_prices():
    """After stepping, at least some prices should have changed."""
    sim = Simulator()
    before = dict(sim._prices)
    sim._step()
    changed = sum(1 for t in TICKER_CONFIG if sim._prices[t] != before[t])
    assert changed > 0, "No prices changed after step"


def test_simulator_price_floor():
    """Prices should never go below 0.01."""
    sim = Simulator()
    # Force very low prices
    for ticker in sim._prices:
        sim._prices[ticker] = 0.02
    sim._step()
    for ticker in sim._prices:
        assert sim._prices[ticker] >= 0.01


# --- Provider interface conformance ---


def test_simulator_conforms_to_interface():
    """Simulator must be a MarketDataProvider with concrete start/stop."""
    assert issubclass(Simulator, MarketDataProvider)
    sim = Simulator()
    assert isinstance(sim, MarketDataProvider)
    assert inspect.iscoroutinefunction(sim.start)
    assert inspect.iscoroutinefunction(sim.stop)


def test_massive_client_conforms_to_interface(monkeypatch):
    """MassiveClient must be a MarketDataProvider with concrete start/stop."""
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    assert issubclass(MassiveClient, MarketDataProvider)
    client = MassiveClient(tickers=list(TICKER_CONFIG.keys()))
    assert isinstance(client, MarketDataProvider)
    assert inspect.iscoroutinefunction(client.start)
    assert inspect.iscoroutinefunction(client.stop)


# --- Provider selection by environment ---


def test_provider_defaults_to_simulator(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert isinstance(create_provider(), Simulator)


def test_provider_uses_massive_when_key_set(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    assert isinstance(create_provider(), MassiveClient)


def test_provider_treats_blank_key_as_simulator(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    assert isinstance(create_provider(), Simulator)


# --- Price cache exposes latest / previous / timestamp ---


def test_cache_exposes_latest_previous_and_timestamp():
    cache = PriceCache()
    first = cache.update("AAPL", 190.0)
    assert first.price == 190.0
    assert first.previous_price == 190.0  # first update: prev == current
    assert first.timestamp
    assert first.direction == "flat"

    second = cache.update("AAPL", 191.5)
    assert second.price == 191.5
    assert second.previous_price == 190.0
    assert second.direction == "up"

    third = cache.update("AAPL", 191.0)
    assert third.direction == "down"


def test_cache_get_and_get_all():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    assert cache.get("AAPL").price == 190.0
    assert cache.get("MISSING") is None
    assert {p.ticker for p in cache.get_all()} == {"AAPL", "GOOGL"}
