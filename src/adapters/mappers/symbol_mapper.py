"""Symbol mapping between internal, IBKR, and Yahoo formats."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolMapping:
    """Mapping for a single symbol across different systems."""

    internal: str  # e.g., "/MGC"
    yahoo: str  # e.g., "MGC=F"
    ibkr_symbol: str  # e.g., "MGC"
    ibkr_exchange: str  # e.g., "COMEX"


class SymbolMapper:
    """Maps symbols between internal, IBKR, and Yahoo Finance formats.

    Internal format: "/<symbol>" (e.g., "/MGC", "/MES")
    Yahoo format: "<symbol>=F" for futures (e.g., "MGC=F", "ES=F")
    IBKR format: "<symbol>" with exchange (e.g., "MGC" on "COMEX")
    """

    # Symbol mappings
    MAPPINGS: dict[str, SymbolMapping] = {
        "/MGC": SymbolMapping("/MGC", "MGC=F", "MGC", "COMEX"),
        "/SIL": SymbolMapping("/SIL", "SI=F", "SIL", "COMEX"),  # Yahoo uses SI=F
        "/M2K": SymbolMapping("/M2K", "RTY=F", "M2K", "CME"),  # Yahoo uses RTY=F
        "/MES": SymbolMapping("/MES", "ES=F", "MES", "CME"),  # Yahoo uses ES=F
        "/MNQ": SymbolMapping("/MNQ", "NQ=F", "MNQ", "CME"),  # Yahoo uses NQ=F
        "/MYM": SymbolMapping("/MYM", "YM=F", "MYM", "CME"),  # Yahoo uses YM=F
        "/MCL": SymbolMapping("/MCL", "CL=F", "MCL", "NYMEX"),  # Yahoo uses CL=F
        "/MNG": SymbolMapping("/MNG", "NG=F", "MNG", "NYMEX"),  # Yahoo uses NG=F
        # Full-size contracts (for Yahoo fallback when micro not available)
        "/GC": SymbolMapping("/GC", "GC=F", "GC", "COMEX"),
        "/SI": SymbolMapping("/SI", "SI=F", "SI", "COMEX"),
        "/ES": SymbolMapping("/ES", "ES=F", "ES", "CME"),
        "/NQ": SymbolMapping("/NQ", "NQ=F", "NQ", "CME"),
        "/CL": SymbolMapping("/CL", "CL=F", "CL", "NYMEX"),
    }

    # Yahoo to internal reverse mapping
    _YAHOO_TO_INTERNAL: dict[str, str] = {
        m.yahoo: m.internal for m in MAPPINGS.values()
    }

    def to_yahoo(self, internal: str) -> str:
        """Convert internal symbol to Yahoo Finance format.

        Args:
            internal: Internal symbol (e.g., "/MGC")

        Returns:
            Yahoo symbol (e.g., "MGC=F")

        Raises:
            ValueError: If symbol not found
        """
        if internal not in self.MAPPINGS:
            raise ValueError(f"Unknown symbol: {internal}")
        return self.MAPPINGS[internal].yahoo

    def from_yahoo(self, yahoo: str) -> str:
        """Convert Yahoo symbol to internal format.

        Args:
            yahoo: Yahoo symbol (e.g., "GC=F")

        Returns:
            Internal symbol (e.g., "/GC")

        Raises:
            ValueError: If symbol not found
        """
        if yahoo not in self._YAHOO_TO_INTERNAL:
            raise ValueError(f"Unknown Yahoo symbol: {yahoo}")
        return self._YAHOO_TO_INTERNAL[yahoo]

    def to_ibkr(self, internal: str) -> tuple[str, str]:
        """Convert internal symbol to IBKR format.

        Args:
            internal: Internal symbol (e.g., "/MGC")

        Returns:
            Tuple of (symbol, exchange) for IBKR

        Raises:
            ValueError: If symbol not found
        """
        if internal not in self.MAPPINGS:
            raise ValueError(f"Unknown symbol: {internal}")
        mapping = self.MAPPINGS[internal]
        return mapping.ibkr_symbol, mapping.ibkr_exchange

    def get_yahoo_fallback(self, internal: str) -> str | None:
        """Get full-size Yahoo symbol as fallback for micro contracts.

        Yahoo doesn't always have good data for micro contracts,
        so we can fall back to the full-size equivalent.

        Args:
            internal: Internal symbol (e.g., "/MGC")

        Returns:
            Full-size Yahoo symbol (e.g., "GC=F") or None if not applicable
        """
        # Map micro to full-size
        micro_to_full = {
            "/MGC": "/GC",
            "/SIL": "/SI",
            "/MES": "/ES",
            "/MNQ": "/NQ",
            "/M2K": "/ES",  # No RTY micro alternative
            "/MYM": "/ES",  # No YM micro alternative
            "/MCL": "/CL",
            "/MNG": "/MNG",  # Keep same
        }

        full = micro_to_full.get(internal)
        if full and full in self.MAPPINGS:
            return self.MAPPINGS[full].yahoo
        return None

    def is_known(self, internal: str) -> bool:
        """Check if symbol is known."""
        return internal in self.MAPPINGS
