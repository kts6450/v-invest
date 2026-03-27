"""
PPO 포트폴리오 최적화 라우터

[흐름]
  실시간 시장 데이터 수집 (Finnhub + Binance)
      → PPO 모델 추론 → 최적 자산 비중 반환
      → TTS용 텍스트 포함 (음성으로 읽어줄 수 있는 형태)

[PPO 모델 인터페이스]
  입력: [가격변동률, RSI, 변동성, 공포탐욕지수, ...] × 자산 수
  출력: 각 자산 비중 합계 = 1.0
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.ppo_agent import PPOAgent
from app.services.data_collector import get_latest_market_state

router    = APIRouter()
ppo_agent = PPOAgent()   # 모듈 로드 시 PPO 모델 초기화


class PortfolioResponse(BaseModel):
    weights:        dict[str, float]  # {"BTC": 0.25, "AAPL": 0.20, ...}
    voice_summary:  str               # TTS로 읽어줄 포트폴리오 요약
    market_state:   dict              # 추론에 사용된 시장 상태
    confidence:     float             # 모델 신뢰도 (Sharpe ratio 기반)


@router.get("/recommend", response_model=PortfolioResponse,
            summary="PPO 기반 최적 포트폴리오 추천")
async def recommend_portfolio():
    """
    현재 시장 상태 → PPO 모델 추론 → 자산 배분 추천

    [TTS 연동]
    voice_summary 필드를 /voice/tts 엔드포인트로 바로 전달하면
    시각 장애인이 음성으로 포트폴리오를 청취 가능
    """
    try:
        market_state = await get_latest_market_state()
        weights      = ppo_agent.predict(market_state)

        # 음성 요약 생성 (TTS 최적화: 짧고 명확하게)
        voice_summary = _build_voice_summary(weights, market_state)

        return PortfolioResponse(
            weights=weights,
            voice_summary=voice_summary,
            market_state=market_state,
            confidence=market_state.get("confidence", 0.0),
        )
    except Exception as e:
        raise HTTPException(500, f"포트폴리오 추천 실패: {str(e)}")


@router.get("/backtest", summary="PPO 모델 백테스트 결과 조회")
async def get_backtest_result(days: int = 30):
    """
    PPO vs Buy&Hold 성과 비교
    결과는 voice_summary 포함하여 음성 청취 가능
    """
    result = ppo_agent.backtest(days=days)
    ppo    = result.get("ppo", {})
    bh     = result.get("buy_and_hold", {})

    voice_summary = (
        f"최근 {days}일 백테스트 결과입니다. "
        f"PPO 모델 수익률 {ppo.get('return', 0):.1f}퍼센트, "
        f"샤프 비율 {ppo.get('sharpe', 0):.2f}. "
        f"단순 보유 전략 수익률 {bh.get('return', 0):.1f}퍼센트, "
        f"샤프 비율 {bh.get('sharpe', 0):.2f}. "
        f"{'PPO 모델이 더 우수합니다.' if ppo.get('sharpe', 0) > bh.get('sharpe', 0) else '단순 보유 전략이 더 우수합니다.'}"
    )
    return {**result, "voice_summary": voice_summary}


def _build_voice_summary(weights: dict, market: dict) -> str:
    """
    포트폴리오 비중을 시각 장애인이 쉽게 이해할 수 있는 문장으로 변환

    [예시 출력]
    "PPO 모델 포트폴리오 추천입니다. 비트코인 25퍼센트,
     엔비디아 20퍼센트, 애플 15퍼센트, 현금 40퍼센트.
     현재 시장 심리는 공포 구간으로, 현금 비중을 높게 유지합니다."
    """
    name_map = {
        "BTC": "비트코인", "ETH": "이더리움", "SOL": "솔라나",
        "AAPL": "애플", "NVDA": "엔비디아", "TSLA": "테슬라", "CASH": "현금",
    }
    parts = []
    for asset, w in sorted(weights.items(), key=lambda x: -x[1]):
        name   = name_map.get(asset, asset)
        pct    = round(w * 100, 1)
        parts.append(f"{name} {pct}퍼센트")

    fng = market.get("fng", 50)
    sentiment = (
        "극도의 공포 구간" if fng < 20 else
        "공포 구간"        if fng < 40 else
        "중립 구간"        if fng < 60 else
        "탐욕 구간"        if fng < 80 else
        "극도의 탐욕 구간"
    )

    return (
        f"PPO 모델 포트폴리오 추천입니다. "
        f"{', '.join(parts)}. "
        f"현재 시장 심리는 {sentiment}으로, 공포탐욕 지수 {fng}입니다."
    )
