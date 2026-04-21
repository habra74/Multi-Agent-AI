"""
tests/test_ticker_normalizer.py
--------------------------------
ticker normalization 및 KRX 지원 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from utils.ticker_normalizer import normalize_ticker, get_display_name, infer_market


class TestNormalizeTicker:

    # ---- US market (default) ----

    def test_us_uppercase(self):
        assert normalize_ticker("aapl") == "AAPL"

    def test_us_already_upper(self):
        assert normalize_ticker("NVDA") == "NVDA"

    def test_us_strip_whitespace(self):
        assert normalize_ticker("  MSFT  ") == "MSFT"

    # ---- KR market: pure digit codes ----

    def test_kr_6digit_appends_ks(self):
        assert normalize_ticker("005930", "KR") == "005930.KS"

    def test_kr_6digit_000660(self):
        assert normalize_ticker("000660", "KR") == "000660.KS"

    def test_kr_already_has_ks_suffix(self):
        assert normalize_ticker("005930.KS", "KR") == "005930.KS"

    def test_kr_ks_suffix_lowercase_normalized(self):
        assert normalize_ticker("005930.ks", "KR") == "005930.KS"

    def test_kr_kq_suffix_kept(self):
        result = normalize_ticker("263750.KQ", "KR")
        assert result == "263750.KQ"

    # ---- Korean alias map ----

    def test_alias_samsung(self):
        assert normalize_ticker("삼성전자") == "005930.KS"

    def test_alias_samsung_short(self):
        assert normalize_ticker("삼성") == "005930.KS"

    def test_alias_sk_hynix(self):
        assert normalize_ticker("SK하이닉스") == "000660.KS"

    def test_alias_naver(self):
        assert normalize_ticker("NAVER") == "035420.KS"

    def test_alias_kakao(self):
        assert normalize_ticker("카카오") == "035720.KS"

    def test_alias_works_regardless_of_market(self):
        # Korean alias should resolve even if market="US"
        assert normalize_ticker("삼성전자", "US") == "005930.KS"
        assert normalize_ticker("삼성전자", "KR") == "005930.KS"

    # ---- Edge cases ----

    def test_empty_string_returned_as_is(self):
        assert normalize_ticker("") == ""

    def test_none_returned_as_is(self):
        assert normalize_ticker(None) is None


class TestGetDisplayName:

    def test_samsung(self):
        assert get_display_name("005930.KS") == "삼성전자"

    def test_aapl(self):
        assert get_display_name("AAPL") == "Apple Inc."

    def test_unknown_returns_ticker(self):
        assert get_display_name("UNKNOWN") == "UNKNOWN"


class TestInferMarket:

    def test_ks_suffix_is_kr(self):
        assert infer_market("005930.KS") == "KR"

    def test_kq_suffix_is_kr(self):
        assert infer_market("263750.KQ") == "KR"

    def test_us_ticker_is_us(self):
        assert infer_market("AAPL") == "US"

    def test_nvda_is_us(self):
        assert infer_market("NVDA") == "US"
