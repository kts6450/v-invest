"""
Vision 에이전트 라우터 - 차트 이미지 → 시각 장애인용 음성 설명 텍스트 생성

[흐름]
  프론트엔드에서 차트 이미지(base64 or URL) 전송
      → GPT-4o Vision 분석
      → 시각 장애인이 이해하기 쉬운 음성 설명 텍스트 반환
      → 프론트엔드에서 TTS로 읽어줌

[핵심 프롬프트 전략]
  - "보다시피" 같은 시각적 표현 금지
  - 구체적 수치와 방향성 명시 ("RSI 72로 과매수 구간")
  - 1분 내 읽을 수 있는 분량 (150~200자)
"""
import base64
import io
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.core.llm_client import get_vision_client, get_gemini_client
from app.core.config import settings

router = APIRouter()

# ── 시각 장애인 최적화 프롬프트 ──
VISION_SYSTEM_PROMPT = """당신은 시각 장애인을 위한 금융 차트 해설사입니다.
차트 이미지를 분석하여 청각으로 이해할 수 있는 설명을 생성하세요.

[반드시 지켜야 할 규칙]
1. "보다시피", "그래프를 보면" 같은 시각적 표현 절대 사용 금지
2. 모든 수치를 명확히 언급 (가격, RSI, 거래량 등)
3. 추세 방향을 명확히 서술 ("상승", "하락", "횡보")
4. 중요 지지/저항 레벨 구체적으로 언급
5. 한국어로 답변, 150자 이내로 간결하게
6. 마지막에 한 문장으로 투자 시사점 제시

[출력 예시]
"AAPL 1시간봉 차트입니다. 현재가 252달러 62센트, 
RSI 41로 중립권입니다. 20일 이동평균선 256달러 13센트 아래에 위치해 단기 약세입니다. 
MACD는 데드크로스 상태입니다. 단기 매수보다는 관망이 적절해 보입니다." """


class ChartUrlRequest(BaseModel):
    """URL로 차트 이미지 전달 시 사용"""
    url:    str
    symbol: str = ""   # 종목명 (프롬프트 보강용)
    period: str = "1d" # 차트 기간


class ChartAnalysisResponse(BaseModel):
    description: str   # TTS로 읽어줄 음성 설명 텍스트
    symbol:      str
    model_used:  str


@router.post("/analyze/upload", response_model=ChartAnalysisResponse,
             summary="차트 이미지 파일 업로드 → 음성 설명")
async def analyze_chart_upload(
    file:   UploadFile = File(...),
    symbol: str        = "",
):
    """
    프론트엔드에서 스크린샷/파일을 직접 업로드할 때 사용
    이미지 → base64 인코딩 → GPT-4o Vision 전달
    """
    image_bytes  = await file.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_type    = file.content_type or "image/png"

    description = await _analyze_with_openai(image_base64, mime_type, symbol)
    return ChartAnalysisResponse(
        description=description,
        symbol=symbol,
        model_used=settings.VISION_MODEL,
    )


@router.post("/analyze/url", response_model=ChartAnalysisResponse,
             summary="차트 이미지 URL → 음성 설명")
async def analyze_chart_url(req: ChartUrlRequest):
    """
    URL로 차트 이미지를 전달받아 GPT-4o Vision으로 분석
    URL 다운로드 실패 시 Yahoo Finance 실제 데이터로 직접 차트 생성 후 분석
    """
    image_bytes = None
    mime_type   = "image/png"

    # URL 다운로드 시도
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(req.url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 1000:
                image_bytes = resp.content
                mime_type   = resp.headers.get("content-type", "image/png").split(";")[0]
    except Exception:
        pass

    # URL 실패 시 Yahoo Finance 데이터로 차트 직접 생성
    if not image_bytes:
        symbol      = req.symbol or "AAPL"
        image_bytes = await _generate_yahoo_chart(symbol)
        mime_type   = "image/png"

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    description  = await _analyze_with_openai(image_base64, mime_type, req.symbol)

    return ChartAnalysisResponse(
        description=description,
        symbol=req.symbol,
        model_used=settings.VISION_MODEL,
    )


@router.get("/analyze/symbol/{symbol}", response_model=ChartAnalysisResponse,
            summary="종목명으로 실시간 차트 생성 후 GPT-4o Vision 분석")
async def analyze_symbol_chart(symbol: str, period: str = "3mo"):
    """
    Yahoo Finance 실시간 데이터 → matplotlib 차트 생성 → GPT-4o Vision 분석 → 음성 설명
    시각 장애인이 종목명만 말하면 전체 분석을 음성으로 제공하는 핵심 플로우
    """
    image_bytes  = await _generate_yahoo_chart(symbol.upper(), period)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    description  = await _analyze_with_openai(image_base64, "image/png", symbol.upper())

    return ChartAnalysisResponse(
        description=description,
        symbol=symbol.upper(),
        model_used=settings.VISION_MODEL,
    )


async def _generate_yahoo_chart(symbol: str, period: str = "3mo") -> bytes:
    """
    Yahoo Finance에서 실제 주가 데이터 조회 후 matplotlib으로 캔들차트 생성
    이동평균선(20일, 60일), 거래량, RSI 포함
    """
    import asyncio, requests as req_lib
    import numpy as np

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
    except ImportError:
        raise HTTPException(500, "matplotlib 미설치. pip install matplotlib")

    # Yahoo Finance 데이터 조회
    range_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y"}
    yf_range  = range_map.get(period, "3mo")
    url       = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?interval=1d&range={yf_range}"
    )
    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(
        None,
        lambda: req_lib.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    )
    result = resp.json()["chart"]["result"][0]
    ts     = result.get("timestamp") or result.get("timestamps")
    ohlcv  = result["indicators"]["quote"][0]

    from datetime import datetime
    dates   = [datetime.fromtimestamp(t) for t in ts]
    closes  = np.array([c or 0 for c in ohlcv["close"]])
    opens   = np.array([c or 0 for c in ohlcv["open"]])
    highs   = np.array([c or 0 for c in ohlcv["high"]])
    lows    = np.array([c or 0 for c in ohlcv["low"]])
    volumes = np.array([c or 0 for c in ohlcv.get("volume", [0]*len(ts))])

    # 이동평균 계산
    def ma(data, n):
        return np.convolve(data, np.ones(n)/n, mode='valid')

    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60) if len(closes) >= 60 else None

    # RSI 계산
    delta = np.diff(closes)
    gain  = np.where(delta > 0, delta, 0)
    loss  = np.where(delta < 0, -delta, 0)
    avg_g = np.convolve(gain, np.ones(14)/14, mode='valid')
    avg_l = np.convolve(loss, np.ones(14)/14, mode='valid')
    rsi   = 100 - (100 / (1 + avg_g / (avg_l + 1e-10)))

    # 차트 그리기
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8),
                                         gridspec_kw={"height_ratios": [3, 1, 1]},
                                         facecolor="#0d1117")
    fig.suptitle(f"{symbol} Stock Analysis", color="white", fontsize=14, fontweight="bold")

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#161b22")
        ax.tick_params(colors="gray")
        ax.spines["bottom"].set_color("#30363d")
        ax.spines["top"].set_color("#30363d")
        ax.spines["left"].set_color("#30363d")
        ax.spines["right"].set_color("#30363d")

    # 캔들차트
    for i, (d, o, h, l, c) in enumerate(zip(dates, opens, highs, lows, closes)):
        color = "#26a641" if c >= o else "#f85149"
        ax1.plot([d, d], [l, h], color=color, linewidth=1)
        width = (dates[-1] - dates[0]).days / len(dates) * 0.6
        rect = Rectangle(
            (mdates.date2num(d) - width/2, min(o, c)),
            width, abs(c - o),
            linewidth=0, facecolor=color
        )
        ax1.add_patch(rect)

    ax1.xaxis_date()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

    # 이동평균
    if len(ma20) > 0:
        ax1.plot(dates[19:], ma20, color="#f78166", linewidth=1, label="MA20", alpha=0.8)
    if ma60 is not None and len(ma60) > 0:
        ax1.plot(dates[59:], ma60, color="#79c0ff", linewidth=1, label="MA60", alpha=0.8)
    ax1.legend(facecolor="#161b22", labelcolor="white", fontsize=8)
    ax1.set_ylabel("Price (USD)", color="gray", fontsize=9)
    ax1.yaxis.label.set_color("gray")

    # 거래량
    vol_colors = ["#26a641" if closes[i] >= opens[i] else "#f85149" for i in range(len(closes))]
    ax2.bar(dates, volumes / 1e6, color=vol_colors, alpha=0.7, width=0.8)
    ax2.set_ylabel("Vol (M)", color="gray", fontsize=8)

    # RSI
    rsi_dates = dates[14:]
    ax3.plot(rsi_dates, rsi, color="#e3b341", linewidth=1)
    ax3.axhline(70, color="#f85149", linestyle="--", linewidth=0.8, alpha=0.7)
    ax3.axhline(30, color="#26a641", linestyle="--", linewidth=0.8, alpha=0.7)
    ax3.fill_between(rsi_dates, rsi, 70, where=(rsi >= 70), alpha=0.2, color="#f85149")
    ax3.fill_between(rsi_dates, rsi, 30, where=(rsi <= 30), alpha=0.2, color="#26a641")
    ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI", color="gray", fontsize=8)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor="#0d1117", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


async def _analyze_with_openai(
    image_base64: str,
    mime_type:    str,
    symbol:       str,
) -> str:
    """
    GPT-4o Vision API 호출 핵심 로직
    실패 시 Gemini Vision으로 자동 fallback
    """
    client = get_vision_client()
    user_prompt = f"{'종목: ' + symbol if symbol else ''} 이 차트를 시각 장애인에게 설명해주세요."

    try:
        response = await client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type":      "image_url",
                            "image_url": {
                                "url":    f"data:{mime_type};base64,{image_base64}",
                                "detail": "high",  # 고해상도 분석
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            max_tokens=300,
            temperature=0.3,  # 낮은 온도 = 일관되고 정확한 설명
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        # GPT-4o 실패 시 Gemini로 fallback
        return await _analyze_with_gemini(image_base64, mime_type, symbol)


async def _analyze_with_gemini(
    image_base64: str,
    mime_type:    str,
    symbol:       str,
) -> str:
    """Gemini Vision fallback"""
    import google.genai as genai
    model  = get_gemini_client()
    prompt = f"{VISION_SYSTEM_PROMPT}\n\n종목: {symbol}\n이 차트를 설명해주세요."
    image_part = {"mime_type": mime_type, "data": image_base64}

    response = model.generate_content([prompt, image_part])
    return response.text.strip()
