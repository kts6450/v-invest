"""
실시간 시장 데이터 수집 서비스

[데이터 소스]
  Binance WebSocket : 암호화폐 실시간 틱 (BTC, ETH, SOL)
  Finnhub REST      : 주식 실시간 시세 + RSI + 재무지표

[구조]
  _market_cache : 최신 시장 상태를 메모리에 캐싱 (PPO 추론에 사용)
  start_binance_websocket() : 서버 시작 시 백그라운드 루프로 실행
  get_latest_market_state() : PPO 모델용 특징 벡터 반환
"""
import asyncio
import json
import websockets
import httpx
from datetime import datetime
from app.core.config import settings

# ── 전역 시장 상태 캐시 (WebSocket이 지속 업데이트) ──
_market_cache: dict = {
    "btc":  {"price": 0, "change": 0},
    "eth":  {"price": 0, "change": 0},
    "sol":  {"price": 0, "change": 0},
    "aapl": {"price": 0, "change": 0, "rsi": 50},
    "nvda": {"price": 0, "change": 0, "rsi": 50},
    "tsla": {"price": 0, "change": 0, "rsi": 50},
    "fng":  50,           # Fear & Greed Index
    "vix":  20,           # 변동성 지수 (ETF 기반)
    "updated_at": None,
}


# ────────────────────────────────
# Binance WebSocket (암호화폐 실시간)
# ────────────────────────────────

async def start_binance_websocket():
    """
    Binance Combined Stream으로 BTC/ETH/SOL 틱 데이터 수신
    서버 시작 시 main.py lifespan에서 asyncio.create_task()로 실행

    [스트림 URL 예시]
    wss://stream.binance.com:9443/stream?streams=btcusdt@ticker/ethusdt@ticker
    """
    streams  = "/".join(f"{s}@ticker" for s in settings.CRYPTO_SYMBOLS)
    url      = f"wss://stream.binance.com:9443/stream?streams={streams}"

    while True:  # 연결 끊기면 자동 재연결
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                print(f"✅ Binance WebSocket 연결: {streams}")
                async for raw_msg in ws:
                    msg    = json.loads(raw_msg)
                    data   = msg.get("data", {})
                    symbol = data.get("s", "").lower().replace("usdt", "")

                    if symbol in _market_cache:
                        _market_cache[symbol] = {
                            "price":  float(data.get("c", 0)),     # 현재가
                            "change": float(data.get("P", 0)),     # 24h 변동률
                            "volume": float(data.get("v", 0)),     # 거래량
                            "high":   float(data.get("h", 0)),
                            "low":    float(data.get("l", 0)),
                        }
                        _market_cache["updated_at"] = datetime.now().isoformat()

        except Exception as e:
            print(f"⚠️ Binance WebSocket 오류: {e}, 5초 후 재연결...")
            await asyncio.sleep(5)


# ────────────────────────────────
# Finnhub REST (주식 실시간)
# ────────────────────────────────

async def refresh_stock_data():
    """
    Finnhub REST API로 주식 시세 갱신 (1분마다 폴링)
    WebSocket 방식보다 단순하지만 무료 플랜에 적합
    """
    symbols = {"aapl": "AAPL", "nvda": "NVDA", "tsla": "TSLA"}
    async with httpx.AsyncClient() as client:
        for key, sym in symbols.items():
            try:
                r = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": sym, "token": settings.FINNHUB_API_KEY},
                    timeout=5,
                )
                d = r.json()
                if d.get("c"):
                    price, prev = d["c"], d.get("pc", d["c"])
                    _market_cache[key] = {
                        "price":  round(price, 2),
                        "change": round((price - prev) / prev * 100, 2),
                    }
                await asyncio.sleep(0.3)  # rate limit
            except Exception:
                pass


# ────────────────────────────────
# PPO 모델용 특징 벡터 반환
# ────────────────────────────────

async def get_latest_market_state() -> dict:
    """
    PPO 모델 추론에 필요한 시장 상태 특징 벡터 반환

    [반환 구조]
    {
      "features": [btc_change, eth_change, sol_change,
                   aapl_change, nvda_change, tsla_change,
                   btc_rsi, nvda_rsi, fng_normalized, vix_normalized],
      "fng": 50,
      "confidence": 0.85,
      ...raw data...
    }
    """
    # 주식 데이터 최신화
    await refresh_stock_data()

    fng = float(_market_cache.get("fng", 50))
    vix = float(_market_cache.get("vix", 20))

    # PPO 입력 특징 정규화 [-1, 1]
    features = [
        _normalize(_market_cache["btc"].get("change", 0),  -10, 10),
        _normalize(_market_cache["eth"].get("change", 0),  -10, 10),
        _normalize(_market_cache["sol"].get("change", 0),  -15, 15),
        _normalize(_market_cache["aapl"].get("change", 0), -5,  5),
        _normalize(_market_cache["nvda"].get("change", 0), -8,  8),
        _normalize(_market_cache["tsla"].get("change", 0), -10, 10),
        _normalize(fng, 0, 100),
        _normalize(vix, 10, 50),
    ]

    return {
        **_market_cache,
        "features":   features,
        "confidence": 1.0 - abs(fng - 50) / 50,  # 극단적 시장 = 낮은 신뢰도
    }


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """값을 [-1, 1] 범위로 정규화"""
    return max(-1.0, min(1.0, (value - min_val) / (max_val - min_val) * 2 - 1))
