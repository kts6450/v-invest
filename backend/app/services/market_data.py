"""
시장 데이터 수집 모듈
- Finnhub API     : 주식 실시간 시세 + 재무지표 + 애널리스트 목표가 + 뉴스 감성
- Binance REST    : 암호화폐 실시간 시세 (BTC, ETH, SOL)
- Alternative.me  : 공포탐욕 지수
- FRED API        : 금리, 실업률, 국채 스프레드, 기대인플레이션
- BLS API         : CPI (소비자물가), PPI (생산자물가)
- NewsAPI         : 주요 인물 뉴스 (젠슨 황, 파월, 트럼프 관세)
- Reddit          : r/wallstreetbets, r/CryptoCurrency 소셜 감성
- Yahoo Finance   : 금/유가/은/S&P500/NASDAQ/VIX (원자재·지수 fallback)
- ExchangeRate    : USD/KRW 환율
"""
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
FRED_KEY    = os.getenv("FRED_API_KEY", "")
BLS_KEY     = os.getenv("BLS_API_KEY", "")
NEWS_KEY    = os.getenv("NEWS_API_KEY", "")

STOCK_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN"]
CRYPTO_PAIRS  = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT", "doge": "DOGEUSDT"}


# ─────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────

def _get(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 12) -> dict:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 1)


def _calc_sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _calc_macd(closes: list[float]) -> dict:
    if len(closes) < 26:
        return {"macd": None, "cross": None}

    def ema(prices, p):
        k, e = 2 / (p + 1), prices[0]
        for v in prices[1:]:
            e = v * k + e * (1 - k)
        return e

    ema12 = ema(closes[-34:], 12)
    ema26 = ema(closes[-34:], 26)
    macd_val = round(ema12 - ema26, 3)
    return {"macd": macd_val, "cross": "bullish" if macd_val > 0 else "bearish"}


# ─────────────────────────────────────────
# 1. Finnhub 주식 데이터
# ─────────────────────────────────────────

def _finnhub(endpoint: str, params: dict) -> dict:
    params["token"] = FINNHUB_KEY
    return _get(f"https://finnhub.io/api/v1/{endpoint}", params)


def _stock_candles(symbol: str) -> dict | None:
    """Yahoo Finance 60일 일봉 → RSI / SMA20 / SMA50 / MACD 계산 (Finnhub 캔들은 유료)"""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
        if len(closes) < 15:
            return None
        return {
            "rsi":   _calc_rsi(closes),
            "sma20": _calc_sma(closes, 20),
            "sma50": _calc_sma(closes, 50),
            "macd":  _calc_macd(closes),
        }
    except Exception:
        return None


def _stock_quote(symbol: str) -> dict | None:
    data = _finnhub("quote", {"symbol": symbol})
    if "error" in data or not data.get("c"):
        return None
    price, prev = data["c"], data.get("pc", data["c"])
    return {
        "price":     round(price, 2),
        "change":    round((price - prev) / prev * 100, 2) if prev else 0,
        "high":      data.get("h"),
        "low":       data.get("l"),
        "prevClose": prev,
    }


def _stock_target(symbol: str) -> dict | None:
    """Finnhub 애널리스트 목표가 (유료) → 추천 추세(무료)로 대체"""
    data = _finnhub("stock/recommendation", {"symbol": symbol})
    if "error" in data or not data:
        return None
    if isinstance(data, list) and data:
        latest = data[0]
        return {
            "strongBuy":  latest.get("strongBuy"),
            "buy":        latest.get("buy"),
            "hold":       latest.get("hold"),
            "sell":       latest.get("sell"),
            "strongSell": latest.get("strongSell"),
            "period":     latest.get("period"),
        }
    return None


def _stock_financials(symbol: str) -> dict | None:
    data = _finnhub("stock/metric", {"symbol": symbol, "metric": "all"})
    m = data.get("metric", {})
    if not m:
        return None
    return {
        "pe":          m.get("peNormalizedAnnual"),
        "eps":         m.get("epsNormalizedAnnual"),
        "marketCap":   m.get("marketCapitalization"),
        "divYield":    m.get("dividendYieldIndicatedAnnual"),
    }


def _stock_sentiment(symbol: str) -> dict | None:
    data = _finnhub("news-sentiment", {"symbol": symbol})
    if "error" in data:
        return None
    s = data.get("sentiment", {})
    return {
        "bullish": s.get("bullishPercent"),
        "bearish": s.get("bearishPercent"),
        "score":   data.get("companyNewsScore"),
    }


def fetch_all_stocks() -> dict:
    result = {}
    for sym in STOCK_SYMBOLS:
        quote = _stock_quote(sym)
        if not quote:
            continue

        candles     = _stock_candles(sym)
        target      = _stock_target(sym)
        financials  = _stock_financials(sym)
        sentiment   = _stock_sentiment(sym)

        rsi = candles["rsi"] if candles else None
        sma20 = candles["sma20"] if candles else None
        sma50 = candles["sma50"] if candles else None
        macd  = candles["macd"]  if candles else None

        rsi_signal = "N/A"
        if rsi is not None:
            if rsi >= 70:   rsi_signal = "🔴 과매수"
            elif rsi <= 30: rsi_signal = "🟢 과매도"
            else:           rsi_signal = "⚪ 중립"

        result[sym.lower()] = {
            **quote,
            "rsi": rsi, "sma20": sma20, "sma50": sma50,
            "macd": macd, "rsiSignal": rsi_signal,
            "aboveSma20": (quote["price"] > sma20) if sma20 else None,
            "aboveSma50": (quote["price"] > sma50) if sma50 else None,
            "target":     target,
            "financials": financials,
            "newsSentiment": sentiment,
        }
        time.sleep(0.35)   # Finnhub 무료 60req/min 제한

    return result


# ─────────────────────────────────────────
# 2. Binance 암호화폐 실시간 시세 (REST)
# ─────────────────────────────────────────

def fetch_crypto() -> dict:
    coins = {}
    for name, pair in CRYPTO_PAIRS.items():
        data = _get("https://api.binance.com/api/v3/ticker/24hr", {"symbol": pair})
        if "error" not in data and data.get("lastPrice"):
            coins[name] = {
                "usd":            float(data["lastPrice"]),
                "usd_24h_change": round(float(data.get("priceChangePercent", 0)), 2),
                "high":           float(data.get("highPrice", 0)),
                "low":            float(data.get("lowPrice", 0)),
                "volume":         float(data.get("volume", 0)),
                "quoteVolume":    float(data.get("quoteVolume", 0)),
            }
        time.sleep(0.1)

    # Fear & Greed Index
    fng_data = _get("https://api.alternative.me/fng/?limit=1")
    fng = {}
    if fng_data.get("data"):
        fng = {
            "value":          fng_data["data"][0]["value"],
            "classification": fng_data["data"][0]["value_classification"],
        }

    return {"coins": coins, "fearGreed": fng}


# ─────────────────────────────────────────
# 3. FRED 매크로 데이터
# ─────────────────────────────────────────

def _fred(series_id: str) -> float | None:
    data = _get("https://api.stlouisfed.org/fred/series/observations", {
        "series_id": series_id,
        "api_key":   FRED_KEY,
        "limit":     1,
        "sort_order": "desc",
        "file_type": "json",
    })
    obs = data.get("observations", [])
    if obs:
        val = obs[0].get("value")
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
    return None


def fetch_macro() -> dict:
    macro = {
        "fedRate":      _fred("FEDFUNDS"),    # 연준 기준금리 (%)
        "unemployment": _fred("UNRATE"),      # 실업률 (%)
        "cpi":          _fred("CPIAUCSL"),    # CPI 수준
        "t10y2y":       _fred("T10Y2Y"),      # 10년-2년 국채 스프레드 (경기침체 선행)
        "t10yie":       _fred("T10YIE"),      # 기대인플레이션 10년
    }
    # 경기침체 신호 해석
    spread = macro.get("t10y2y")
    macro["recessionSignal"] = "⚠️ 역전 (침체 위험)" if spread is not None and spread < 0 else "정상"
    return macro


# ─────────────────────────────────────────
# 4. BLS 물가지수 (CPI / PPI)
# ─────────────────────────────────────────

def fetch_bls() -> dict:
    """BLS CPI/PPI 수집 (타임아웃 시 FRED CPI로 대체)"""
    try:
        payload = {
            "seriesid":        ["CUUR0000SA0", "WPUFD4"],
            "registrationkey": BLS_KEY,
        }
        r = requests.post(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            json=payload, timeout=8     # 짧게 설정, 느리면 FRED fallback
        )
        r.raise_for_status()
        result = {}
        for series in r.json().get("Results", {}).get("series", []):
            sid   = series["seriesID"]
            items = series.get("data", [])
            if items:
                val    = float(items[0]["value"])
                year   = items[0].get("year")
                period = items[0].get("periodName")
                if sid == "CUUR0000SA0":
                    result["cpi"]       = val
                    result["cpiPeriod"] = f"{year} {period}"
                elif sid == "WPUFD4":
                    result["ppi"]       = val
                    result["ppiPeriod"] = f"{year} {period}"
        return result
    except Exception:
        # BLS 타임아웃 시 FRED CPIAUCSL로 대체
        cpi_fred = _fred("CPIAUCSL")
        ppi_fred = _fred("PPIACO")
        return {
            "cpi":       cpi_fred,
            "cpiPeriod": "FRED 최신",
            "ppi":       ppi_fred,
            "ppiPeriod": "FRED 최신",
            "source":    "FRED (BLS fallback)",
        }


# ─────────────────────────────────────────
# 5. NewsAPI 주요 인물 뉴스
# ─────────────────────────────────────────

def fetch_news() -> dict:
    queries = {
        "tech_leaders":  "Jensen Huang OR Elon Musk OR Sam Altman AI",
        "macro_policy":  "Federal Reserve Jerome Powell interest rate OR Trump tariff",
        "crypto_news":   "Bitcoin Ethereum cryptocurrency ETF regulation",
    }
    news = {}
    for key, q in queries.items():
        data = _get("https://newsapi.org/v2/everything", {
            "q": q, "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": NEWS_KEY,
        })
        if data.get("articles"):
            news[key] = [
                {
                    "title":       a["title"],
                    "source":      a["source"]["name"],
                    "publishedAt": a["publishedAt"],
                }
                for a in data["articles"][:5]
            ]
        time.sleep(0.3)
    return news


# ─────────────────────────────────────────
# 6. Reddit 소셜 감성 (공개 JSON API)
# ─────────────────────────────────────────

def fetch_reddit() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (AI-Investment-Analyst/1.0)"}
    result  = {}
    subs    = ["wallstreetbets", "CryptoCurrency"]

    for sub in subs:
        data  = _get(f"https://www.reddit.com/r/{sub}/hot.json?limit=5", headers=headers)
        posts = data.get("data", {}).get("children", [])
        if posts:
            result[sub] = [
                {
                    "title":    p["data"]["title"],
                    "score":    p["data"]["score"],
                    "comments": p["data"]["num_comments"],
                    "upvoteRatio": p["data"].get("upvote_ratio"),
                }
                for p in posts[:5]
            ]
        time.sleep(0.5)

    return result


# ─────────────────────────────────────────
# 7. 환율 + 원자재 + 지수 (Finnhub ETF 실시간)
#
#  ETF 대체 매핑:
#   GLD  → 금 (1/10 oz 기준, 실제 금 가격 ≈ GLD × 10)
#   SLV  → 은 (1 oz 기준, 실제 은 가격 ≈ SLV)
#   USO  → WTI 유가 ETF
#   SPY  → S&P 500 (실제 S&P500 ≈ SPY × 10)
#   QQQ  → NASDAQ-100
#   UVXY → VIX 변동성 ETF (VIX 대체)
# ─────────────────────────────────────────

# Finnhub ETF 대체 티커
_ETF_MAP = {
    "gold":   ("GLD",  10.0),   # GLD 가격 × 10 ≈ 금 oz당 USD
    "silver": ("SLV",   1.0),   # SLV 가격 ≈ 은 oz당 USD
    "oil":    ("USO",   1.0),   # USO ETF 유가 추적
    "sp500":  ("SPY",  10.0),   # SPY × 10 ≈ S&P500 지수
    "nasdaq": ("QQQ",   1.0),   # QQQ = NASDAQ-100
    "vix":    ("UVXY",  1.0),   # UVXY = 변동성 ETF
}


def _finnhub_etf(ticker: str, multiplier: float = 1.0) -> dict:
    """Finnhub ETF 실시간 시세 조회"""
    data = _finnhub("quote", {"symbol": ticker})
    if "error" in data or not data.get("c"):
        return {"price": None, "change": None, "ticker": ticker}
    price    = round(data["c"] * multiplier, 2)
    prev     = data.get("pc", data["c"])
    pct      = round((data["c"] - prev) / prev * 100, 2) if prev else 0
    return {
        "price":  price,
        "change": pct,
        "ticker": ticker,
        "raw":    round(data["c"], 2),  # ETF 실제 가격 (참고용)
    }


def fetch_forex_and_commodities() -> dict:
    # USD/KRW (ExchangeRate-API)
    ex  = _get("https://api.exchangerate-api.com/v4/latest/USD")
    krw = ex.get("rates", {}).get("KRW")

    result = {"usdKrw": krw}
    for key, (ticker, mult) in _ETF_MAP.items():
        result[key] = _finnhub_etf(ticker, mult)
        time.sleep(0.2)  # Finnhub rate limit 보호

    return result


# ─────────────────────────────────────────
# 통합 수집
# ─────────────────────────────────────────

def collect_market_data() -> dict:
    print("📡 시장 데이터 수집 시작...")

    stocks = fetch_all_stocks()
    print(f"  ✅ 주식 {len(stocks)}종목 (Finnhub)")

    crypto_raw = fetch_crypto()
    crypto = {
        **crypto_raw["coins"],
        "fngValue":  crypto_raw["fearGreed"].get("value"),
        "fngClass":  crypto_raw["fearGreed"].get("classification"),
    }
    print(f"  ✅ 암호화폐 {len(crypto_raw['coins'])}종목 (Binance REST)")

    macro = fetch_macro()
    print(f"  ✅ 매크로 (FRED): 금리={macro.get('fedRate')}%, 실업률={macro.get('unemployment')}%")

    bls = fetch_bls()
    print(f"  ✅ 물가 (BLS): CPI={bls.get('cpi')}, PPI={bls.get('ppi')}")

    news = fetch_news()
    print(f"  ✅ 뉴스 (NewsAPI): {len(news)}개 카테고리")

    reddit = fetch_reddit()
    print(f"  ✅ Reddit: {list(reddit.keys())}")

    forex = fetch_forex_and_commodities()
    print(f"  ✅ 환율/원자재/지수 (Finnhub ETF 실시간): 금=${forex.get('gold',{}).get('price')} 유가=${forex.get('oil',{}).get('price')} S&P={forex.get('sp500',{}).get('price')}")

    return {
        "timestamp": datetime.now().isoformat(),
        "stocks":    stocks,
        "crypto":    crypto,
        "macro":     macro,
        "bls":       bls,
        "news":      news,
        "reddit":    reddit,
        "forex":     forex,
    }
