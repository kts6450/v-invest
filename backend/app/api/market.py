"""
시장 데이터 API
GET /market-data           - 주식(Finnhub) + 암호화폐(Binance) 실시간 시세
GET /market-data/full      - 모든 데이터 (주식 + 크립토 + 매크로 + 뉴스 등)
GET /market-data/crypto    - 암호화폐만 (Binance)
GET /market-data/stocks    - 주식만 (Finnhub)
GET /market-data/macro     - 매크로 지표 (FRED + BLS)
GET /market-data/history/{symbol} - 차트용 히스토리 (Yahoo Finance)
"""
import asyncio
import os
import requests as req
from datetime import datetime, timezone, date, timedelta
from time import time

from dotenv import load_dotenv
from fastapi import APIRouter

from app.services.market_data import (
    fetch_crypto,       # Binance REST
    fetch_macro,        # FRED
    fetch_news,         # NewsAPI
    fetch_forex_and_commodities,
    fetch_all_stocks,   # Finnhub (full, 느림)
)

load_dotenv()
FINNHUB_KEY  = os.getenv("FINNHUB_API_KEY", "")

router = APIRouter()

# ── 캐시 (30초) ──
_cache: dict = {}
CACHE_TTL = 30

STOCK_SYMBOLS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]


def _cached(key: str, fn):
    now = time()
    if key in _cache and now - _cache[key]["ts"] < CACHE_TTL:
        return _cache[key]["data"]
    data = fn()
    _cache[key] = {"ts": now, "data": data}
    return data


# ── Finnhub 빠른 quote (price + change only, 대시보드용) ──
def _finnhub_quote(symbol: str) -> dict | None:
    """Finnhub /quote — 실시간 가격 + 등락률"""
    try:
        r = req.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=8,
        )
        d = r.json()
        price = d.get("c")
        prev  = d.get("pc")
        if not price:
            return None
        change = round((price - prev) / prev * 100, 2) if prev else 0
        return {
            "price":  round(price, 2),
            "change": change,
            "high":   d.get("h"),
            "low":    d.get("l"),
            "open":   d.get("o"),
            "prev":   round(prev, 2) if prev else None,
            "source": "Finnhub",
        }
    except Exception:
        return None


def _fetch_finnhub_stocks() -> dict:
    """Finnhub로 STOCK_SYMBOLS 전체 실시간 시세"""
    result = {}
    for sym in STOCK_SYMBOLS:
        data = _finnhub_quote(sym)
        if data:
            result[sym.lower()] = data
    return result


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────

@router.post("", summary="실시간 시세 (POST — n8n/외부 서비스 연동)")
@router.get("", summary="실시간 시세 (Finnhub 주식 + Binance 크립토)")
async def get_market_data():
    """
    대시보드 메인 시세 엔드포인트 (30초 캐시).
    - 주식: Finnhub API (AAPL, NVDA, TSLA, MSFT, GOOGL, AMZN, META)
    - 크립토: Binance REST (BTC, ETH, SOL)
    """
    loop = asyncio.get_event_loop()

    stocks_task = loop.run_in_executor(None, lambda: _cached("stocks_finnhub", _fetch_finnhub_stocks))
    crypto_task = loop.run_in_executor(None, lambda: _cached("crypto_binance", fetch_crypto))

    stocks, crypto = await asyncio.gather(stocks_task, crypto_task)

    return {
        "stocks":    stocks,
        "crypto":    crypto,
        "timestamp": int(time()),
        "sources":   {"stocks": "Finnhub", "crypto": "Binance"},
    }


@router.get("/crypto", summary="암호화폐 시세 (Binance)")
async def get_crypto():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("crypto_binance", fetch_crypto))


@router.get("/stocks", summary="주식 시세 (Finnhub 실시간)")
async def get_stocks():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("stocks_finnhub", _fetch_finnhub_stocks))


@router.get("/macro", summary="매크로 지표 (FRED + BLS)")
async def get_macro():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("macro", fetch_macro))


@router.get("/commodities", summary="원자재 + 환율 (Finnhub ETF)")
async def get_commodities():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("commodities", fetch_forex_and_commodities))


@router.get("/news", summary="주요 뉴스 (NewsAPI)")
async def get_news():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("news", fetch_news))


@router.get("/news/feed", summary="실시간 뉴스 피드 (Finnhub + NewsAPI 통합)")
async def get_news_feed(limit: int = 30):
    """
    세이브티커 스타일 실시간 뉴스 피드.
    - Finnhub 마켓 뉴스 (Reuters, CNBC, Bloomberg)
    - Finnhub 주요 종목 뉴스 (AAPL, NVDA, TSLA, BTC)
    - NewsAPI 비즈니스 헤드라인
    중복 제거 후 최신순 정렬.
    """
    from datetime import date, timedelta

    def _fetch():
        articles = []
        seen_titles: set = set()

        def _add(items: list, source_tag: str):
            for n in items:
                title = (n.get("headline") or n.get("title") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                articles.append({
                    "title":     title,
                    "summary":   (n.get("summary") or n.get("description") or "")[:200],
                    "url":       n.get("url") or n.get("related") or "",
                    "source":    n.get("source") or n.get("author") or source_tag,
                    "image":     n.get("image") or n.get("urlToImage") or "",
                    "timestamp": n.get("datetime") or n.get("publishedAt") or "",
                    "category":  n.get("category") or source_tag,
                    "related":   n.get("related") or "",
                })

        # 1. Finnhub 일반 마켓 뉴스 (Reuters, CNBC 등)
        try:
            r = req.get("https://finnhub.io/api/v1/news",
                params={"category": "general", "token": FINNHUB_KEY}, timeout=10)
            _add(r.json()[:20], "Market")
        except Exception:
            pass

        # 2. Finnhub 주요 종목별 뉴스
        today    = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=5)).isoformat()
        for sym in ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN"]:
            try:
                r = req.get("https://finnhub.io/api/v1/company-news",
                    params={"symbol": sym, "from": week_ago, "to": today,
                            "token": FINNHUB_KEY}, timeout=8)
                _add(r.json()[:5], sym)
            except Exception:
                pass

        # 3. Finnhub 크립토 뉴스
        try:
            r = req.get("https://finnhub.io/api/v1/news",
                params={"category": "crypto", "token": FINNHUB_KEY}, timeout=8)
            _add(r.json()[:10], "Crypto")
        except Exception:
            pass

        # 4. NewsAPI 비즈니스 헤드라인
        NEWS_KEY = os.getenv("NEWS_API_KEY", "")
        if NEWS_KEY:
            try:
                r = req.get("https://newsapi.org/v2/top-headlines",
                    params={"category": "business", "language": "en",
                            "pageSize": 10, "apiKey": NEWS_KEY}, timeout=8)
                _add(r.json().get("articles", []), "Business")
            except Exception:
                pass

        # 최신순 정렬 (timestamp → 숫자로 통일)
        def _ts_key(a):
            ts = a.get("timestamp", 0)
            if isinstance(ts, (int, float)):
                return ts
            try:
                from datetime import datetime
                return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
            except Exception:
                return 0

        articles.sort(key=_ts_key, reverse=True)
        return {"articles": articles[:limit], "total": len(articles)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("news_feed", _fetch))


def _translate_to_korean(articles: list) -> list:
    """
    OpenAI GPT를 사용해 뉴스 제목+요약을 한국어로 배치 번역.
    단일 API 호출로 전체 처리 (비용 절감).
    """
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
    if not OPENAI_KEY:
        return articles

    # 번역할 텍스트 준비 (제목 + 요약)
    texts = []
    for a in articles:
        title   = a.get("title", "")
        summary = a.get("summary", "")
        texts.append(f"TITLE: {title}\nSUMMARY: {summary}" if summary else f"TITLE: {title}")

    numbered = "\n---\n".join(f"[{i+1}]\n{t}" for i, t in enumerate(texts))

    prompt = (
        "다음은 미국 주식/금융 뉴스 기사 목록입니다. "
        "각 기사의 TITLE과 SUMMARY를 자연스러운 한국어로 번역해 주세요. "
        "금융/투자 용어는 업계 표준 한국어 표현을 사용하세요. "
        "원본 번호([1], [2], ...)와 형식을 그대로 유지하고, "
        "TITLE: / SUMMARY: 레이블도 그대로 유지하세요. "
        "SUMMARY가 없는 경우 TITLE만 번역하세요.\n\n"
        + numbered
    )

    try:
        # JSON 배열 방식으로 요청 — 파싱이 훨씬 안정적
        items_json = [
            {"id": i, "title": a.get("title",""), "summary": (a.get("summary") or "")[:150]}
            for i, a in enumerate(articles)
        ]
        import json as _json
        prompt2 = (
            "다음 JSON 배열의 각 항목에서 title과 summary를 한국어로 번역하세요. "
            "금융/투자 전문 용어는 한국 금융업계 표준 표현을 사용하세요. "
            "반드시 동일한 JSON 구조로만 응답하세요 (id, title_ko, summary_ko 필드). "
            "summary가 비어있으면 summary_ko도 빈 문자열로 두세요.\n\n"
            + _json.dumps(items_json, ensure_ascii=False)
        )
        r = req.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt2}],
                "temperature": 0.1,
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
            },
            timeout=40,
        )
        raw = r.json()["choices"][0]["message"]["content"]
        parsed = _json.loads(raw)
        # GPT가 {"items": [...]} 또는 {"translations": [...]} 또는 바로 리스트로 줄 수 있음
        translated = parsed if isinstance(parsed, list) else next(
            (v for v in parsed.values() if isinstance(v, list)), []
        )
        for item in translated:
            idx = item.get("id")
            if idx is not None and idx < len(articles):
                if item.get("title_ko"):
                    articles[idx]["title_ko"]   = item["title_ko"]
                if item.get("summary_ko"):
                    articles[idx]["summary_ko"] = item["summary_ko"]
    except Exception:
        pass

    return articles


@router.get("/news/feed/ko", summary="실시간 뉴스 피드 (한국어 번역)")
async def get_news_feed_korean(limit: int = 20):
    """
    뉴스 피드를 GPT-4o-mini로 한국어 번역하여 반환.
    번역 결과는 5분간 캐시됨.
    """
    def _fetch_and_translate():
        # 먼저 영문 피드 가져오기 (캐시 활용)
        raw = _cached("news_feed", lambda: None)
        if raw is None:
            # 캐시 없으면 직접 수집 (간략 버전)
            articles = []
            seen: set = set()

            def _add(items, tag):
                for n in items:
                    title = (n.get("headline") or n.get("title") or "").strip()
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    articles.append({
                        "title":     title,
                        "summary":   (n.get("summary") or n.get("description") or "")[:200],
                        "url":       n.get("url") or "",
                        "source":    n.get("source") or tag,
                        "image":     n.get("image") or n.get("urlToImage") or "",
                        "timestamp": n.get("datetime") or n.get("publishedAt") or "",
                        "category":  tag,
                    })

            try:
                r = req.get("https://finnhub.io/api/v1/news",
                    params={"category": "general", "token": FINNHUB_KEY}, timeout=10)
                _add(r.json()[:15], "Market")
            except Exception:
                pass
            raw = {"articles": articles[:limit]}

        articles = raw.get("articles", [])[:limit]
        return {"articles": _translate_to_korean(articles), "total": len(articles)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("news_feed_ko", _fetch_and_translate))


@router.get("/history/{symbol}", summary="차트용 가격 히스토리 (Yahoo Finance)")
async def get_price_history(symbol: str, period: str = "3mo"):
    """
    일봉 종가 히스토리 — 차트 렌더링 전용.
    Finnhub 캔들은 유료이므로 Yahoo Finance 무료 API 사용.
    symbol: AAPL, NVDA, TSLA, MSFT, AMZN, BTC-USD, ETH-USD, SOL-USD 등
    period: 1mo / 3mo / 6mo / 1y
    """
    yf_period = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y"}.get(period, "3mo")

    def _fetch():
        try:
            r = req.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "1d", "range": yf_period},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            r.raise_for_status()
            result     = r.json()["chart"]["result"][0]
            timestamps = result.get("timestamp") or result.get("timestamps") or []
            closes     = result["indicators"]["quote"][0].get("close", [])
            data = [
                {"t": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m/%d"), "v": round(c, 2)}
                for ts, c in zip(timestamps, closes) if c is not None
            ]
            return {"symbol": symbol, "period": yf_period, "data": data, "source": "Yahoo Finance"}
        except Exception as e:
            return {"symbol": symbol, "period": yf_period, "data": [], "error": str(e)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached(f"history_{symbol}_{yf_period}", _fetch))


@router.get("/events", summary="경제 이벤트 캘린더 (실적 발표 + 경제지표 일정)")
async def get_events():
    """
    향후 30일간 경제 이벤트:
    - 실적 발표: Finnhub earnings calendar (주요 종목 우선)
    - 경제지표: FOMC / CPI / NFP / PPI 공식 발표 일정 계산
    """
    def _fetch():
        today     = date.today()
        end_date  = today + timedelta(days=45)
        events    = []

        # ── 1. Finnhub 실적 발표 ──────────────────────
        MAJOR = {"AAPL","NVDA","TSLA","MSFT","GOOGL","AMZN","META",
                 "NFLX","INTC","AMD","JPM","GS","BAC","V","TSM"}
        try:
            r = req.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": today.isoformat(), "to": end_date.isoformat(),
                        "token": FINNHUB_KEY},
                timeout=10,
            )
            calendar = r.json().get("earningsCalendar", [])
            # 주요 종목 먼저, 나머지는 EPS 추정치 있는 것만
            seen_dates: dict[str, list] = {}
            for e in calendar:
                sym = e.get("symbol", "")
                dt  = e.get("date", "")
                if not dt:
                    continue
                is_major = sym in MAJOR
                has_eps  = e.get("epsEstimate") is not None
                if not is_major and not has_eps:
                    continue
                seen_dates.setdefault(dt, []).append({
                    "date":     dt,
                    "type":     "earnings",
                    "symbol":   sym,
                    "label":    f"{sym} 실적 발표",
                    "detail":   f"EPS 추정 {e['epsEstimate']:.2f}" if has_eps else "EPS 미발표",
                    "priority": 1 if is_major else 2,
                    "source":   "Finnhub",
                })
            for dt_events in seen_dates.values():
                # 날짜당 최대 3개, 주요 종목 우선
                dt_events.sort(key=lambda x: x["priority"])
                events.extend(dt_events[:3])
        except Exception:
            pass

        # ── 2. 경제지표 발표 일정 (FOMC / CPI / NFP / PPI) ──
        # FOMC 2026 예정일 (회의 2일차 = 발표일)
        fomc_2026 = [
            date(2026, 1, 28), date(2026, 3, 18), date(2026, 5, 6),
            date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
            date(2026, 10, 28), date(2026, 12, 10),
        ]
        # CPI 발표일 (BLS 2026 공식 스케줄)
        cpi_2026 = [
            date(2026, 1, 14), date(2026, 2, 11), date(2026, 3, 11),
            date(2026, 4, 10), date(2026, 5, 13), date(2026, 6, 11),
            date(2026, 7, 10), date(2026, 8, 12), date(2026, 9, 11),
            date(2026, 10, 14), date(2026, 11, 12), date(2026, 12, 10),
        ]
        # NFP (비농업고용지수) — 매월 첫 번째 금요일
        def first_friday(y: int, m: int) -> date:
            d = date(y, m, 1)
            return d + timedelta(days=(4 - d.weekday()) % 7)

        nfp_2026 = [first_friday(2026, m) for m in range(1, 13)]

        macro_schedule = (
            [(d, "FOMC", "연준 금리 결정 발표", "rgba(99,102,241,0.8)")  for d in fomc_2026] +
            [(d, "CPI",  "소비자물가지수 발표",  "rgba(16,185,129,0.8)") for d in cpi_2026]  +
            [(d, "NFP",  "비농업고용지수 발표",  "rgba(245,158,11,0.8)") for d in nfp_2026]
        )
        for (evt_date, etype, label, color) in macro_schedule:
            if today <= evt_date <= end_date:
                events.append({
                    "date":     evt_date.isoformat(),
                    "type":     "macro",
                    "symbol":   etype,
                    "label":    label,
                    "detail":   f"미국 {label}",
                    "priority": 0,
                    "color":    color,
                    "source":   "BLS/Fed 공식 스케줄",
                })

        # ── 정렬 (날짜 → priority) ──
        events.sort(key=lambda x: (x["date"], x["priority"]))
        return {"events": events[:30], "range": {"from": today.isoformat(), "to": end_date.isoformat()}}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _cached("events", _fetch))


@router.get("/full", summary="전체 시장 데이터 (Finnhub + Binance + FRED + BLS + NewsAPI + Reddit)")
async def get_full():
    """
    n8n 워크플로우 및 RAG 분석에서 사용하는 종합 데이터 엔드포인트.
    - 주식: Finnhub (재무지표 + 애널리스트 목표가 + 뉴스 감성 포함, 느림 ~15s)
    - 크립토: Binance REST
    - 매크로: FRED
    - 원자재/환율: Finnhub ETF
    """
    loop = asyncio.get_event_loop()
    stocks, crypto, macro, commodities = await asyncio.gather(
        loop.run_in_executor(None, lambda: _cached("stocks_full", fetch_all_stocks)),
        loop.run_in_executor(None, lambda: _cached("crypto_binance", fetch_crypto)),
        loop.run_in_executor(None, lambda: _cached("macro", fetch_macro)),
        loop.run_in_executor(None, lambda: _cached("commodities", fetch_forex_and_commodities)),
    )
    return {
        "stocks":      stocks,
        "crypto":      crypto,
        "macro":       macro,
        "commodities": commodities,
        "timestamp":   int(time()),
        "sources":     {
            "stocks":      "Finnhub (quote + metrics + sentiment)",
            "crypto":      "Binance REST",
            "macro":       "FRED",
            "commodities": "Finnhub ETF",
        },
    }
