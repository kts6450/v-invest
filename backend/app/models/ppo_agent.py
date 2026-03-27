"""
PPO 포트폴리오 최적화 에이전트 (Stable-Baselines3)

[학습 환경 설명]
  상태(State)  : [BTC변동%, ETH변동%, SOL변동%, AAPL변동%, NVDA변동%, TSLA변동%,
                  공포탐욕지수(정규화), VIX(정규화)]  → 8차원 벡터
  행동(Action) : 각 자산의 투자 비중 [BTC, ETH, SOL, AAPL, NVDA, TSLA, CASH]
                 softmax → 합계 1.0
  보상(Reward) : 일일 샤프 비율 (수익/변동성)

[파일 구조]
  PPOAgent.predict() : 학습된 모델 로드 → 추론
  PPOAgent.backtest() : 과거 데이터로 성과 측정
  PortfolioEnv        : Gymnasium 환경 (모델 학습 시 사용)
"""
import numpy as np
from pathlib import Path
from app.core.config import settings


class PPOAgent:
    """
    PPO 포트폴리오 에이전트 래퍼
    모델 파일(ppo_portfolio.zip)이 없으면 균등 배분 반환
    """

    def __init__(self):
        self.model      = None
        self.model_path = settings.MODEL_DIR / settings.PPO_MODEL_FILE
        self._load_model()

    def _load_model(self):
        """저장된 PPO 모델 로드 (stable-baselines3)"""
        if not self.model_path.exists():
            print(f"⚠️ PPO 모델 없음: {self.model_path} → 균등 배분 모드")
            return
        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(str(self.model_path))
            print(f"✅ PPO 모델 로드 완료: {self.model_path}")
        except ImportError:
            print("⚠️ stable-baselines3 미설치 → 균등 배분 모드")
        except Exception as e:
            print(f"⚠️ PPO 로드 오류: {e}")

    def predict(self, market_state: dict) -> dict[str, float]:
        """
        시장 상태 → PPO 추론 → 자산별 투자 비중

        [입력] market_state["features"] : 8차원 정규화 벡터
        [출력] {"BTC": 0.25, "ETH": 0.10, ..., "CASH": 0.40}
        """
        assets = settings.ASSETS

        if self.model is None:
            # 모델 없을 때: 공포탐욕 기반 단순 규칙 배분
            return self._rule_based_weights(market_state)

        features  = np.array(market_state.get("features", [0.0] * 8), dtype=np.float32)
        action, _ = self.model.predict(features, deterministic=True)

        # softmax → 합계 1.0 정규화
        exp_action = np.exp(action - action.max())
        weights    = exp_action / exp_action.sum()

        return {asset: round(float(w), 4) for asset, w in zip(assets, weights)}

    def backtest(self, days: int = 30) -> dict:
        """
        PPO 전략 vs Buy & Hold 백테스트
        실제 구현 시: yfinance로 과거 데이터 로드 → 시뮬레이션

        [현재] 더미 데이터 반환 (뼈대)
        """
        return {
            "period_days": days,
            "ppo": {
                "return":    12.5,
                "sharpe":    1.34,
                "max_dd":   -8.2,
                "win_rate":  0.62,
            },
            "buy_and_hold": {
                "return":    9.1,
                "sharpe":    0.87,
                "max_dd":  -15.6,
                "win_rate":  None,
            },
        }

    def _rule_based_weights(self, market_state: dict) -> dict[str, float]:
        """
        PPO 모델 없을 때 공포탐욕 지수 기반 규칙 배분
        - 공포(FNG < 30): 현금 비중 ↑, 위험자산 ↓
        - 탐욕(FNG > 70): 위험자산 비중 ↑, 현금 ↓
        """
        fng = market_state.get("fng", 50)

        if fng < 30:    # 극도의 공포 → 방어적
            return {"BTC": 0.10, "ETH": 0.05, "SOL": 0.05,
                    "AAPL": 0.15, "NVDA": 0.10, "TSLA": 0.05, "CASH": 0.50}
        elif fng < 50:  # 공포 → 중립
            return {"BTC": 0.15, "ETH": 0.10, "SOL": 0.05,
                    "AAPL": 0.20, "NVDA": 0.15, "TSLA": 0.05, "CASH": 0.30}
        elif fng < 70:  # 중립 → 공격적
            return {"BTC": 0.20, "ETH": 0.15, "SOL": 0.10,
                    "AAPL": 0.20, "NVDA": 0.20, "TSLA": 0.05, "CASH": 0.10}
        else:           # 탐욕 → 매우 공격적
            return {"BTC": 0.25, "ETH": 0.20, "SOL": 0.10,
                    "AAPL": 0.20, "NVDA": 0.20, "TSLA": 0.05, "CASH": 0.00}


# ── PPO 학습 환경 (별도 학습 스크립트에서 사용) ──

class PortfolioEnv:
    """
    Gymnasium 호환 커스텀 투자 환경
    실제 학습은 train_ppo.py 별도 스크립트로 실행

    [사용법]
      env   = PortfolioEnv(price_data)
      model = PPO("MlpPolicy", env, verbose=1)
      model.learn(total_timesteps=100_000)
      model.save("models/ppo_portfolio")
    """

    def __init__(self, price_data: np.ndarray):
        """
        price_data : (T, n_assets) 형태의 과거 가격 데이터
        """
        self.data    = price_data
        self.n_assets = price_data.shape[1] + 1  # +1 for CASH
        self.t        = 0

    def reset(self):
        self.t = 0
        return self._get_obs()

    def step(self, action: np.ndarray):
        """
        action : 각 자산 투자 비중 (softmax 적용 전 로짓)
        reward : 일일 포트폴리오 샤프 비율
        """
        weights   = _softmax(action)
        returns   = self.data[self.t + 1] / self.data[self.t] - 1
        portfolio_return = float(np.dot(weights[:-1], returns))

        # 보상: 샤프 비율 근사 (일일 수익 / 일일 변동성)
        std    = max(float(returns.std()), 1e-8)
        reward = portfolio_return / std

        self.t += 1
        done  = self.t >= len(self.data) - 2
        return self._get_obs(), reward, done, {}

    def _get_obs(self) -> np.ndarray:
        if self.t == 0:
            return np.zeros(8, dtype=np.float32)
        changes = (self.data[self.t] / self.data[self.t - 1] - 1).astype(np.float32)
        return np.clip(changes, -0.15, 0.15)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()
