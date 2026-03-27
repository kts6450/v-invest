"""
AI 투자 분석 파이프라인 (n8n 완전 대체)

[n8n → Python 대응표]
  스케줄 트리거       → APScheduler (main.py에서 등록)
  시장 데이터 수집    → market_data.collect_market_data()
  데이터 통합         → integrate_data()
  데이터 품질 검증    → validate_data()
  기술적 지표 계산    → calc_technicals()
  심리 점수 계산      → calc_sentiment()
  AI 프롬프트 생성    → build_prompt()
  AI 에이전트         → run_analyst_agent()
  리스크 전문가 AI    → run_risk_agent()
  AI 자기검증(편집장) → run_editor_agent()
  리포트 품질 평가    → evaluate_quality()
  RAG 투자 조언       → rag_service.query()
  리포트 포맷팅       → format_report()
  리포트 저장         → save_report()
  SSE 브로드캐스트    → _broadcast()  (프론트엔드 실시간 업데이트)

[진행 상태 스트리밍]
  run_pipeline()이 실행되는 동안 _status_queue를 통해
  프론트엔드에 각 단계 진행 상황을 SSE로 실시간 전달
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.rag_service import get_rag_chain

from app.services.market_data import collect_market_data as _collect

# ── 전역 상태 ──
_status_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
_report_store: list[dict]    = []   # 메모리 히스토리 (최대 30건)
_is_running:   bool          = False

REPORTS_FILE = Path(__file__).parent.parent.parent / "data" / "reports.json"
REPORTS_FILE.parent.mkdir(exist_ok=True)


# ══════════════════════════════════════════
# 메인 파이프라인 진입점
# ══════════════════════════════════════════

async def run_pipeline(triggered_by: str = "schedule") -> dict:
    """
    n8n 전체 워크플로우를 대체하는 메인 함수
    APScheduler 또는 /analysis/run API 요청으로 호출

    [단계]
    1. 시장 데이터 수집  → collect_market_data()
    2. 데이터 통합       → integrate_data()
    3. 품질 검증         → validate_data()
    4. 기술적 지표       → calc_technicals()
    5. 심리 점수         → calc_sentiment()
    6. AI 프롬프트       → build_prompt()
    7. 투자분석가 AI     → run_analyst_agent()
    8. 리스크 전문가 AI  → run_risk_agent()
    9. 편집장 AI         → run_editor_agent()
    10. 품질 평가        → evaluate_quality()
    11. RAG 조언         → get_rag_advice()
    12. 리포트 포맷팅    → format_report()
    13. 저장 + 브로드캐스트
    """
    global _is_running
    if _is_running:
        return {"status": "already_running", "message": "파이프라인이 이미 실행 중입니다"}

    _is_running = True
    started_at  = datetime.now()

    try:
        # ── 1. 시장 데이터 수집 ──
        await _push("collecting", "📡 시장 데이터 수집 중... (Finnhub + Binance + FRED)")
        raw_data = await asyncio.get_event_loop().run_in_executor(None, _collect)

        # ── 2~3. 통합 + 품질 검증 ──
        await _push("integrating", "🔄 데이터 통합 및 품질 검증 중...")
        data    = integrate_data(raw_data)
        quality = validate_data(data)
        if quality["warnings"]:
            await _push("warning", f"⚠️ 품질 경고: {', '.join(quality['warnings'][:3])}")

        # ── 4~6. 지표 계산 + 프롬프트 ──
        await _push("processing", "📊 기술적 지표 계산 및 심리 점수 산출 중...")
        data = calc_technicals(data)
        data = calc_sentiment(data)
        prompt = build_prompt(data)

        await _push("scoring", f"🎯 시장 심리 점수: {data['sentimentScore']}점 {data['sentimentLabel']}")

        # ── 7. 투자분석가 AI ──
        await _push("analyst", "🤖 AI 투자분석가 리포트 작성 중...")
        main_analysis = await run_analyst_agent(prompt)

        # ── 8. 리스크 전문가 AI ──
        await _push("risk", "🛡️ 리스크 전문가 AI 검토 중...")
        risk_analysis = await run_risk_agent(data, main_analysis)

        # ── 9. 편집장 AI 자기검증 ──
        await _push("editor", "✏️ AI 편집장 자기검증 중...")
        final_analysis = await run_editor_agent(data, main_analysis, risk_analysis)

        # ── 10. 품질 평가 ──
        await _push("evaluating", "📋 리포트 품질 평가 중...")
        report_quality = evaluate_quality(final_analysis, risk_analysis)

        await _push("quality", f"📋 품질: {report_quality['grade']}등급 ({report_quality['score']}/100)")

        # ── 11. RAG 투자 조언 ──
        await _push("rag", "📚 RAG 기반 과거 리포트 참조 중...")
        rag_advice = await get_rag_advice(data)

        # ── 12. 최종 리포트 포맷팅 ──
        await _push("formatting", "📝 최종 리포트 작성 중...")
        report = format_report(
            data=data,
            main_analysis=main_analysis,
            risk_analysis=risk_analysis,
            final_analysis=final_analysis,
            rag_advice=rag_advice,
            quality=report_quality,
        )

        # ── 13. 저장 + RAG 추가 + SSE 알림 ──
        await _push("saving", "💾 리포트 저장 중...")
        await save_report(report)

        elapsed = round((datetime.now() - started_at).total_seconds())
        await _push("done", f"✅ 완료! ({elapsed}초 소요) 새 리포트가 도착했습니다.", report=report)

        return {"status": "ok", "elapsed_seconds": elapsed, "report": report}

    except Exception as e:
        await _push("error", f"❌ 파이프라인 오류: {str(e)}")
        raise
    finally:
        _is_running = False


# ══════════════════════════════════════════
# 단계별 처리 함수 (n8n Code 노드 대체)
# ══════════════════════════════════════════

def integrate_data(raw: dict) -> dict:
    """
    [n8n: 데이터 통합 노드 대체]
    market_data.py의 raw 출력을 분석에 적합한 구조로 정규화
    """
    crypto_raw = raw.get("crypto", {})
    forex_raw  = raw.get("forex",  {})

    crypto = {
        "btc":  _coin(crypto_raw, "btc"),
        "eth":  _coin(crypto_raw, "eth"),
        "sol":  _coin(crypto_raw, "sol"),
        "xrp":  _coin(crypto_raw, "xrp"),
        "doge": _coin(crypto_raw, "doge"),
        "fngValue": crypto_raw.get("fngValue", 50),
        "fngClass":  crypto_raw.get("fngClass", "Neutral"),
    }

    forex       = {"usdKrw": forex_raw.get("usdKrw")}
    commodities = {
        "gold":   forex_raw.get("gold",   {"price": "-", "change": "0"}),
        "oil":    forex_raw.get("oil",    {"price": "-", "change": "0"}),
        "silver": forex_raw.get("silver", {"price": "-", "change": "0"}),
    }
    indices = {
        "sp500":  forex_raw.get("sp500",  {"price": "-", "change": "0"}),
        "nasdaq": forex_raw.get("nasdaq", {"price": "-", "change": "0"}),
        "vix":    forex_raw.get("vix",    {"price": "20", "change": "0"}),
    }

    raw_stocks = raw.get("stocks", {})
    stocks     = {sym: {"price": d.get("price"), "change": d.get("change"),
                        "high": d.get("high"), "low": d.get("low")}
                  for sym, d in raw_stocks.items()}

    news_raw = raw.get("news", {})
    news = {
        "tech_leaders": [a["title"] for a in news_raw.get("tech_leaders", [])],
        "macro_policy": [a["title"] for a in news_raw.get("macro_policy", [])],
        "crypto_news":  [a["title"] for a in news_raw.get("crypto_news",  [])],
    }

    return {
        "timestamp":  raw.get("timestamp", datetime.now().isoformat()),
        "crypto":     crypto,
        "forex":      forex,
        "commodities": commodities,
        "indices":    indices,
        "stocks":     stocks,
        "rawStocks":  raw_stocks,
        "news":       news,
        "reddit":     raw.get("reddit", {}),
        "macro":      raw.get("macro",  {}),
        "bls":        raw.get("bls",    {}),
    }


def validate_data(data: dict) -> dict:
    """[n8n: 데이터 품질 검증 노드 대체]"""
    errors = []
    crypto = data.get("crypto", {})

    if not isinstance(crypto.get("btc", {}).get("usd"), (int, float)):
        errors.append("BTC 데이터 누락")
    if not isinstance(crypto.get("eth", {}).get("usd"), (int, float)):
        errors.append("ETH 데이터 누락")

    for sym, s in data.get("stocks", {}).items():
        if not s.get("price") or s["price"] <= 0:
            errors.append(f"{sym}: 가격 비정상")
        if abs(float(s.get("change") or 0)) > 50:
            errors.append(f"{sym}: 변동률 이상({s['change']}%)")

    vix = float(data.get("indices", {}).get("vix", {}).get("price") or 20)
    if vix > 100:
        errors.append("VIX 비정상값")

    return {"valid": len(errors) == 0, "warnings": errors}


def calc_technicals(data: dict) -> dict:
    """[n8n: 기술적 지표 계산 노드 대체]"""
    technicals = {}
    for sym, raw in data.get("rawStocks", {}).items():
        rsi   = raw.get("rsi")
        sma20 = raw.get("sma20")
        sma50 = raw.get("sma50")
        price = data["stocks"].get(sym, {}).get("price")

        signal = "N/A"
        if rsi is not None:
            if rsi >= 70:   signal = "🔴 과매수"
            elif rsi <= 30: signal = "🟢 과매도"
            else:           signal = "⚪ 중립"

        technicals[sym] = {
            "rsi":  rsi,   "sma20": sma20, "sma50": sma50,
            "macd": raw.get("macd"),
            "signal":      signal,
            "aboveSma":    (price > sma20) if (price and sma20) else None,
            "aboveSma50":  (price > sma50) if (price and sma50) else None,
            "target":      raw.get("target"),
            "financials":  raw.get("financials"),
            "newsSentiment": raw.get("newsSentiment"),
        }
    return {**data, "technicals": technicals}


def calc_sentiment(data: dict) -> dict:
    """[n8n: 심리 점수 계산 노드 대체]"""
    score = 0.0
    crypto = data.get("crypto", {})

    # 암호화폐 24h 변동
    btc_ch = float(crypto.get("btc", {}).get("usd_24h_change") or 0)
    eth_ch = float(crypto.get("eth", {}).get("usd_24h_change") or 0)
    sol_ch = float(crypto.get("sol", {}).get("usd_24h_change") or 0)
    score += ((btc_ch + eth_ch + sol_ch) / 3) * 2.5

    # 공포탐욕 지수
    fng = int(crypto.get("fngValue") or 50)
    score += (fng - 50) * 0.3

    # 주식 변동
    stock_changes = [float(s.get("change") or 0) for s in data.get("stocks", {}).values()]
    if stock_changes:
        score += (sum(stock_changes) / len(stock_changes)) * 3

    # VIX
    vix = float(data.get("indices", {}).get("vix", {}).get("price") or 20)
    score += -15 if vix > 30 else -5 if vix > 20 else 5

    # 금 (안전자산)
    gold_ch = float(data.get("commodities", {}).get("gold", {}).get("change") or 0)
    score -= gold_ch * 1.5

    # RSI 평균
    rsi_vals = [t["rsi"] for t in data.get("technicals", {}).values() if t.get("rsi") is not None]
    if rsi_vals:
        score += (sum(rsi_vals) / len(rsi_vals) - 50) * 0.2

    # 매크로 (FRED)
    macro  = data.get("macro", {})
    t10y2y = macro.get("t10y2y")
    if t10y2y is not None:
        score += -12 if t10y2y < 0 else 5 if t10y2y > 1 else 0
    fed_rate = macro.get("fedRate")
    if fed_rate is not None:
        score += -5 if fed_rate > 5 else 5 if fed_rate < 2 else 0

    score = max(-100, min(100, round(score)))

    if score >= 30:    label = "🟢 Strong Buy"
    elif score >= 10:  label = "🟡 Buy"
    elif score >= -10: label = "⚪ Neutral"
    elif score >= -30: label = "🟠 Sell"
    else:              label = "🔴 Strong Sell"

    return {**data, "sentimentScore": score, "sentimentLabel": label}


def build_prompt(data: dict) -> str:
    """[n8n: AI 프롬프트 생성 노드 대체]"""
    c    = data["crypto"]
    s    = data["stocks"]
    idx  = data["indices"]
    com  = data["commodities"]
    fx   = data["forex"]
    tech = data.get("technicals", {})
    macro = data.get("macro", {})
    bls  = data.get("bls", {})

    def tech_line(sym: str) -> str:
        t = tech.get(sym, {})
        line = f"RSI={t.get('rsi', 'N/A')} {t.get('signal', '')} | SMA20=${t.get('sma20', 'N/A')} | MACD {(t.get('macd') or {}).get('cross', 'N/A')}"
        tgt = t.get("target") or {}
        if tgt.get("strongBuy") is not None:
            line += f" | 추천: 강매수{tgt['strongBuy']} 매수{tgt['buy']} 보유{tgt['hold']} 매도{tgt['sell']}"
        fin = t.get("financials") or {}
        if fin.get("pe"):
            line += f" | P/E {fin['pe']:.1f}"
        return line

    def news_section(key: str, label: str) -> str:
        items = (data.get("news") or {}).get(key, [])
        if not items:
            return ""
        return f"[{label}]\n" + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(items[:3]))

    def reddit_section() -> str:
        wsb    = (data.get("reddit") or {}).get("wallstreetbets", [])
        crypto = (data.get("reddit") or {}).get("CryptoCurrency", [])
        out    = ""
        if wsb:
            out += "[WSB 핫 포스트]\n" + "\n".join(f"  - {p['title']} (추천수: {p['score']})" for p in wsb[:3]) + "\n"
        if crypto:
            out += "[r/CryptoCurrency]\n" + "\n".join(f"  - {p['title']} (추천수: {p['score']})" for p in crypto[:3])
        return out

    return f"""당신은 골드만삭스 출신 수석 금융 애널리스트입니다.
아래 멀티소스 실시간 데이터를 종합 분석하여 한국어로 전문 투자 리포트를 작성하세요.

=== 시장 심리 점수 ===
{data['sentimentScore']}점 (-100~+100) | {data['sentimentLabel']}

=== 암호화폐 (Binance) ===
BTC ${(c['btc'].get('usd') or 0):,.0f} ({(c['btc'].get('usd_24h_change') or 0):.2f}%) | ETH ${(c['eth'].get('usd') or 0):,.0f} ({(c['eth'].get('usd_24h_change') or 0):.2f}%)
SOL ${c['sol'].get('usd') or 0} | XRP ${c['xrp'].get('usd') or 0} | DOGE ${c['doge'].get('usd') or 0}
공포탐욕: {c['fngValue']} ({c['fngClass']})

=== 환율/원자재 ===
USD/KRW ₩{(fx.get('usdKrw') or 0):,.0f}
금 ${com['gold'].get('price') or '-'} ({com['gold'].get('change') or '0'}%) | 은 ${com['silver'].get('price') or '-'} | WTI ${com['oil'].get('price') or '-'}

=== 미국 주식 + 기술적 지표 (Finnhub) ===
AAPL  ${s.get('aapl',  {}).get('price') or '-'} ({s.get('aapl',  {}).get('change') or '0'}%) | {tech_line('aapl')}
TSLA  ${s.get('tsla',  {}).get('price') or '-'} ({s.get('tsla',  {}).get('change') or '0'}%) | {tech_line('tsla')}
NVDA  ${s.get('nvda',  {}).get('price') or '-'} ({s.get('nvda',  {}).get('change') or '0'}%) | {tech_line('nvda')}
MSFT  ${s.get('msft',  {}).get('price') or '-'} ({s.get('msft',  {}).get('change') or '0'}%) | {tech_line('msft')}
GOOGL ${s.get('googl', {}).get('price') or '-'} ({s.get('googl', {}).get('change') or '0'}%) | {tech_line('googl')}
AMZN  ${s.get('amzn',  {}).get('price') or '-'} ({s.get('amzn',  {}).get('change') or '0'}%) | {tech_line('amzn')}

=== 시장 지수 ===
S&P500 {idx['sp500'].get('price') or '-'} ({idx['sp500'].get('change') or '0'}%) | NASDAQ {idx['nasdaq'].get('price') or '-'} | VIX {idx['vix'].get('price') or '-'}

=== 매크로 지표 (FRED + BLS) ===
연준 기준금리: {macro.get('fedRate') or '-'}% | 실업률: {macro.get('unemployment') or '-'}%
국채 스프레드(10Y-2Y): {macro.get('t10y2y') or '-'} → {macro.get('recessionSignal') or '-'}
CPI: {bls.get('cpi') or macro.get('cpi') or '-'} | PPI: {bls.get('ppi') or '-'}

=== 뉴스 (NewsAPI) ===
{news_section('tech_leaders', '테크 리더 (젠슨황·머스크·알트만)')}
{news_section('macro_policy', '연준·정책 (파월·트럼프 관세)')}
{news_section('crypto_news', '암호화폐·규제')}

=== Reddit 소셜 감성 ===
{reddit_section()}

분석 형식:
📌 시장 총평 (심리점수 + 매크로 지표 종합)
💰 암호화폐 전망 (공포탐욕 + Binance 데이터 기반)
📈 종목별 월가 의견 (RSI/SMA/애널리스트 추천 반드시 인용)
🏛️ 매크로 영향 분석 (FRED 금리+국채스프레드 → 증시 영향)
📰 뉴스 교차검증 (NewsAPI + Reddit 소셜 감성 비교)
⚠️ 리스크 요인 (3가지)
💡 투자 전략 (데이터 기반, 2-3 bullet)"""


# ══════════════════════════════════════════
# AI 에이전트 함수 (n8n Agent 노드 대체)
# ══════════════════════════════════════════

ANALYST_SYSTEM = """당신은 골드만삭스 수석 금융 애널리스트 출신으로, 15년간 미국 주식·암호화폐·원자재 시장을 분석해온 전문가입니다.

[분석 프레임워크]
1. 기술적 분석: RSI(14일), SMA(20/50일) 크로스오버를 반드시 해석. RSI>70 과매수, RSI<30 과매도.
2. 펀더멘털: P/E, 성장성, 섹터 포지션 고려.
3. 심리 분석: Fear & Greed Index를 타이밍 판단에 활용.
4. 뉴스 영향도: 복수 소스 교차검증, 단일 소스는 신뢰도 낮게.

[출력 규칙]
- 각 종목 목표가(상향/하향/중립)와 근거 제시.
- 수치 인용 시 반드시 출처 지표명 병기.
- 확신도를 높음/중간/낮음으로 표기.
- 모든 응답은 한국어로."""

RISK_SYSTEM = """당신은 JP모건 리스크 관리 부서 출신 20년 경력 시니어 리스크 매니저입니다.
투자 분석가의 리포트에서 간과된 위험 요소를 찾아내는 것이 핵심 임무입니다.

[출력 규칙]
- 숨겨진 리스크 최소 3가지 도출.
- 각 리스크별 발생확률(높음/중간/낮음)과 영향도 매트릭스.
- 최악의 시나리오 예상 손실률(%) 제시.
- 구체적 헷지 전략 제안.
- 절대 투자분석가 의견에 동조하지 말 것. 항상 반대 관점으로 검증."""

EDITOR_SYSTEM = """당신은 블룸버그 편집국 출신 시니어 편집장입니다.
투자분석가와 리스크 전문가 두 명의 리포트를 교차 검토하여 최종 통합 리포트를 작성합니다.

[출력 규칙]
- 의견 일치: ✅, 충돌: ⚖️, 데이터 오류 의심: ⚠️로 표시.
- 최종 판단을 '강력매수/매수/중립/매도/강력매도'로 제시.
- 신뢰도 등급 A~D 부여 및 근거 명시.
- 단순 나열 금지. 반드시 비교·분석·종합."""


async def run_analyst_agent(prompt: str) -> str:
    """[n8n: AI 에이전트(투자분석가) 노드 대체] temperature=0.7"""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    r = await client.chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=[
            {"role": "system",  "content": ANALYST_SYSTEM},
            {"role": "user",    "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )
    return r.choices[0].message.content.strip()


async def run_risk_agent(data: dict, main_analysis: str) -> str:
    """[n8n: 리스크 전문가 AI 노드 대체] temperature=0.5"""
    idx  = data.get("indices", {})
    com  = data.get("commodities", {})
    fx   = data.get("forex", {})
    crypto = data.get("crypto", {})

    risk_prompt = f"""아래는 투자 분석가의 리포트입니다. 간과된 리스크를 찾아내세요.

[메인 분석가 리포트]
{main_analysis}

[현재 핵심 데이터]
VIX: {idx.get('vix', {}).get('price') or '-'} | 공포탐욕: {crypto.get('fngValue')} ({crypto.get('fngClass')})
금: ${com.get('gold', {}).get('price') or '-'}({com.get('gold', {}).get('change') or '0'}%) | USD/KRW: {(fx.get('usdKrw') or 0):,.0f}

반드시 분석:
1. 🔍 숨겨진 리스크 3가지
2. 💥 최악의 시나리오 (확률 포함)
3. 🛡️ 헷지 전략 추천
4. 📊 포트폴리오 리스크 점수 (1~10)"""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    r = await client.chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=[
            {"role": "system", "content": RISK_SYSTEM},
            {"role": "user",   "content": risk_prompt},
        ],
        temperature=0.5,
        max_tokens=1000,
    )
    return r.choices[0].message.content.strip()


async def run_editor_agent(data: dict, main_analysis: str, risk_analysis: str) -> str:
    """[n8n: AI 자기검증(편집장) 노드 대체] temperature=0.3"""
    reflection_prompt = f"""두 전문가의 분석을 교차 검토하고 최종 통합 리포트를 작성하세요.

[1차: 투자 분석가 리포트]
{main_analysis}

[2차: 리스크 전문가 의견]
{risk_analysis}

수행 사항:
1. 논리적 모순 확인
2. 데이터와 결론 일치 여부 검증
3. 낙관적↔보수적 균형 맞춰 최종 통합 리포트 작성
4. 의견 일치: ✅, 충돌: ⚖️ 표시"""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    r = await client.chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=[
            {"role": "system", "content": EDITOR_SYSTEM},
            {"role": "user",   "content": reflection_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )
    return r.choices[0].message.content.strip()


def evaluate_quality(final_analysis: str, risk_analysis: str) -> dict:
    """[n8n: 리포트 품질 평가 노드 대체]"""
    score  = 0
    checks = []

    required = ["시장 총평", "암호화폐", "종목", "포트폴리오", "리스크", "전략"]
    for section in required:
        if section in final_analysis:
            score += 10
            checks.append(f"✅ {section} 섹션 포함")
        else:
            checks.append(f"❌ {section} 섹션 누락")

    stocks = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN"]
    covered = sum(1 for s in stocks if s in final_analysis)
    score  += covered * 3

    for kw, label in [("RSI", "RSI"), ("SMA", "SMA/이동평균")]:
        if kw in final_analysis:
            score += 5
            checks.append(f"✅ {label} 포함")
        else:
            checks.append(f"⚠️ {label} 미포함")

    if risk_analysis and len(risk_analysis) > 100:
        score += 5
        checks.append("✅ 리스크 분석 반영")

    score = min(100, score)
    grade = (
        "A+" if score >= 90 else "A"  if score >= 80 else
        "B+" if score >= 70 else "B"  if score >= 60 else
        "C"  if score >= 50 else "D"
    )
    return {
        "score":         score,
        "grade":         grade,
        "checks":        checks,
        "stockCoverage": f"{covered}/6",
        "evaluatedAt":   datetime.now().isoformat(),
    }


async def get_rag_advice(data: dict) -> str:
    """[n8n: RAG 투자 조언 요청 노드 대체] 내부 함수 직접 호출"""
    try:
        rag   = await get_rag_chain()
        query = (
            f"현재 시장 요약: BTC ${data['crypto']['btc'].get('usd', 0):,.0f}, "
            f"심리점수 {data['sentimentScore']}점({data['sentimentLabel']}). "
            f"지금 시장 상황에서 투자 전략과 주목할 종목을 추천해줘."
        )
        result = rag.query(query, top_k=5)
        return result.get("answer", "(RAG 답변 없음)")
    except Exception as e:
        return f"(RAG 오류: {e})"


def format_report(
    data: dict,
    main_analysis:  str,
    risk_analysis:  str,
    final_analysis: str,
    rag_advice:     str,
    quality:        dict,
) -> dict:
    """[n8n: 리포트 포맷팅 노드 대체] 프론트엔드에서 바로 쓸 수 있는 구조로 반환"""
    c    = data["crypto"]
    s    = data["stocks"]
    idx  = data["indices"]
    com  = data["commodities"]
    fx   = data["forex"]
    macro = data.get("macro", {})
    bls  = data.get("bls",   {})
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    def e(val):
        return "📈" if float(val or 0) >= 0 else "📉"

    # 헤더 요약 (Discord 스타일 → 웹에서도 그대로 렌더링 가능)
    summary = (
        f"📊 **AI 월가 투자 리포트** ({today})\n\n"
        f"🎯 심리 점수: **{data['sentimentScore']}점** {data['sentimentLabel']}\n"
        f"📋 리포트 품질: **{quality['grade']}등급** ({quality['score']}/100) | 종목 커버: {quality['stockCoverage']}\n\n"
        f"━━━ 💰 암호화폐 (Binance) ━━━\n"
        f"{e(c['btc'].get('usd_24h_change'))} BTC ${(c['btc'].get('usd') or 0):,.0f} ({(c['btc'].get('usd_24h_change') or 0):.1f}%) | "
        f"{e(c['eth'].get('usd_24h_change'))} ETH ${(c['eth'].get('usd') or 0):,.0f}\n"
        f"SOL ${c['sol'].get('usd') or 0} | XRP ${c['xrp'].get('usd') or 0} | 공포탐욕 {c['fngValue']}\n\n"
        f"━━━ 📈 주요 주식 ━━━\n"
        f"AAPL ${s.get('aapl', {}).get('price') or '-'} | NVDA ${s.get('nvda', {}).get('price') or '-'} | TSLA ${s.get('tsla', {}).get('price') or '-'}\n"
        f"S&P500 {idx['sp500'].get('price') or '-'} | VIX {idx['vix'].get('price') or '-'}\n\n"
        f"━━━ 🏦 매크로 ━━━\n"
        f"금리 {macro.get('fedRate') or '-'}% | CPI {bls.get('cpi') or macro.get('cpi') or '-'} | 국채스프레드 {macro.get('t10y2y') or '-'}"
    )

    return {
        "date":           today,
        "summary":        summary,
        "mainAnalysis":   main_analysis,
        "riskAnalysis":   risk_analysis,
        "finalAnalysis":  final_analysis,
        "ragAdvice":      rag_advice,
        "quality":        quality,
        "sentimentScore": data["sentimentScore"],
        "sentimentLabel": data["sentimentLabel"],
        "marketData":     {
            "crypto": data["crypto"],
            "stocks": data["stocks"],
            "indices": data["indices"],
            "commodities": data["commodities"],
            "forex": data["forex"],
            "macro": macro,
        },
    }


async def save_report(report: dict):
    """리포트를 파일 + 메모리에 저장하고 RAG 벡터 DB에 추가"""
    global _report_store

    # 메모리 히스토리 (최대 30건)
    _report_store.append(report)
    if len(_report_store) > 30:
        _report_store = _report_store[-30:]

    # JSON 파일 영속 저장
    try:
        existing = json.loads(REPORTS_FILE.read_text()) if REPORTS_FILE.exists() else []
        existing.append(report)
        REPORTS_FILE.write_text(json.dumps(existing[-30:], ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"⚠️ 리포트 파일 저장 실패: {e}")

    # RAG 벡터 DB에 추가 (다음 질문 시 이 리포트 참조)
    try:
        rag = await get_rag_chain()
        content = f"{report['summary']}\n\n{report['finalAnalysis']}"
        rag.kb.add_report(content, "daily_report", datetime.now().strftime("%Y-%m-%d"), "pipeline")
    except Exception as e:
        print(f"⚠️ RAG 저장 실패: {e}")


def get_report_history(limit: int = 10) -> list[dict]:
    """저장된 리포트 히스토리 반환"""
    if _report_store:
        return _report_store[-limit:]
    # 메모리 없으면 파일에서 로드
    if REPORTS_FILE.exists():
        try:
            return json.loads(REPORTS_FILE.read_text())[-limit:]
        except Exception:
            pass
    return []


def get_pipeline_status() -> dict:
    return {
        "is_running":    _is_running,
        "report_count":  len(_report_store),
        "last_run":      _report_store[-1]["date"] if _report_store else None,
    }


# ══════════════════════════════════════════
# SSE 브로드캐스트 헬퍼
# ══════════════════════════════════════════

async def _push(step: str, message: str, report: dict = None):
    """프론트엔드 SSE로 파이프라인 진행 상황 실시간 전달"""
    event = {"step": step, "message": message, "ts": datetime.now().isoformat()}
    if report:
        event["report"] = {
            "sentimentScore": report.get("sentimentScore"),
            "sentimentLabel": report.get("sentimentLabel"),
            "grade":          report.get("quality", {}).get("grade"),
            "preview":        report.get("summary", "")[:300],
        }
    if not _status_queue.full():
        await _status_queue.put(event)
    print(f"[Pipeline] {message}")


async def pipeline_event_stream() -> AsyncGenerator[str, None]:
    """
    /analysis/stream SSE 엔드포인트에서 사용
    프론트엔드 EventSource가 파이프라인 진행 상황을 실시간 수신
    """
    while True:
        try:
            event = await asyncio.wait_for(_status_queue.get(), timeout=30)
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"


# ── 헬퍼 ──
def _coin(crypto_raw: dict, key: str) -> dict:
    d = crypto_raw.get(key, {})
    if isinstance(d, dict):
        return d
    return {"usd": d, "usd_24h_change": 0}
