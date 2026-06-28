"""Abstract market data provider interface."""

from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    """Abstract base for market data providers."""

    @abstractmethod
    async def start(self) -> None:
        """Start producing price updates."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop producing price updates."""

    def add_ticker(self, ticker: str) -> None:
        """Start tracking/pricing a new ticker. Override in subclasses."""

    def remove_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker. Override in subclasses."""


# Module-level registry of the active provider so request handlers can ask the
# market layer to start/stop tracking tickers without threading the instance
# through every router.
_active_provider: MarketDataProvider | None = None


def set_active_provider(provider: MarketDataProvider | None) -> None:
    """Register the running provider (called from the app lifespan)."""
    global _active_provider
    _active_provider = provider


def get_active_provider() -> MarketDataProvider | None:
    """Return the running provider, or None if not started."""
    return _active_provider
