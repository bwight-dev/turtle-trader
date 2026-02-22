"""Unit tests for symbol mapper."""

import pytest

from src.adapters.mappers.symbol_mapper import SymbolMapper


@pytest.fixture
def mapper():
    """Create symbol mapper."""
    return SymbolMapper()


class TestToYahoo:
    """Tests for internal to Yahoo conversion."""

    def test_mgc_to_yahoo(self, mapper):
        """Test /MGC maps to MGC=F."""
        assert mapper.to_yahoo("/MGC") == "MGC=F"

    def test_mes_to_yahoo(self, mapper):
        """Test /MES maps to ES=F (full size equivalent)."""
        assert mapper.to_yahoo("/MES") == "ES=F"

    def test_m2k_to_yahoo(self, mapper):
        """Test /M2K maps to RTY=F."""
        assert mapper.to_yahoo("/M2K") == "RTY=F"

    def test_sil_to_yahoo(self, mapper):
        """Test /SIL maps to SI=F."""
        assert mapper.to_yahoo("/SIL") == "SI=F"

    def test_unknown_raises(self, mapper):
        """Test unknown symbol raises ValueError."""
        with pytest.raises(ValueError, match="Unknown symbol"):
            mapper.to_yahoo("/UNKNOWN")


class TestFromYahoo:
    """Tests for Yahoo to internal conversion."""

    def test_gc_from_yahoo(self, mapper):
        """Test GC=F maps to /GC."""
        assert mapper.from_yahoo("GC=F") == "/GC"

    def test_es_from_yahoo(self, mapper):
        """Test ES=F maps to /ES."""
        assert mapper.from_yahoo("ES=F") == "/ES"

    def test_unknown_raises(self, mapper):
        """Test unknown Yahoo symbol raises ValueError."""
        with pytest.raises(ValueError, match="Unknown Yahoo symbol"):
            mapper.from_yahoo("UNKNOWN=F")


class TestToIBKR:
    """Tests for internal to IBKR conversion."""

    def test_mgc_to_ibkr(self, mapper):
        """Test /MGC maps to (MGC, COMEX)."""
        symbol, exchange = mapper.to_ibkr("/MGC")
        assert symbol == "MGC"
        assert exchange == "COMEX"

    def test_mes_to_ibkr(self, mapper):
        """Test /MES maps to (MES, CME)."""
        symbol, exchange = mapper.to_ibkr("/MES")
        assert symbol == "MES"
        assert exchange == "CME"


class TestFallback:
    """Tests for Yahoo fallback symbols."""

    def test_mgc_fallback_to_gc(self, mapper):
        """Test /MGC falls back to GC=F."""
        assert mapper.get_yahoo_fallback("/MGC") == "GC=F"

    def test_mes_fallback_to_es(self, mapper):
        """Test /MES falls back to ES=F."""
        assert mapper.get_yahoo_fallback("/MES") == "ES=F"

    def test_full_size_no_fallback(self, mapper):
        """Test full-size contracts have no fallback."""
        # /GC is already full-size, no mapping needed
        assert mapper.get_yahoo_fallback("/GC") is None


class TestIsKnown:
    """Tests for symbol validation."""

    def test_known_symbols(self, mapper):
        """Test known symbols return True."""
        assert mapper.is_known("/MGC") is True
        assert mapper.is_known("/MES") is True
        assert mapper.is_known("/M2K") is True

    def test_unknown_symbols(self, mapper):
        """Test unknown symbols return False."""
        assert mapper.is_known("/UNKNOWN") is False
        assert mapper.is_known("MGC") is False  # Missing slash
