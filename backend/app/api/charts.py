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
    Finnhub 차트 URL 또는 외부 이미지 URL로 분석할 때 사용
    URL → 이미지 다운로드 → base64 → GPT-4o Vision
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(req.url, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(400, "이미지 다운로드 실패")
        image_bytes  = resp.content
        mime_type    = resp.headers.get("content-type", "image/png")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    description  = await _analyze_with_openai(image_base64, mime_type, req.symbol)

    return ChartAnalysisResponse(
        description=description,
        symbol=req.symbol,
        model_used=settings.VISION_MODEL,
    )


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
