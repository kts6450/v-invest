"""
PPO 포트폴리오 최적화 에이전트 (Stable-Baselines3)

학습된 모델은 train_ppo.py로 생성된 ppo_portfolio.zip 파일을 사용합니다.

[입력 형식]
  관측 벡터: 6개 자산 × 20일 일별수익률 = 120차원 float32 벡터
  (BTC, ETH, SOL, AAPL, NVDA, TSLA 순서)

[출력 형식]
  {"BTC": 0.25, "ETH": 0.10, ..., "CASH": 0.40}  합계 1.0
"""
import json
import numpy as np
import requests
from pathlib import Path
from datetime import datetime, timedelta

from app.core.config import settings

ASSETS      = ["BTC", "ETH", "SOL", "AAPL", "NVDA", "TSLA", "CASH"]
SYMBOLS     = ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "NVDA", "TSLA"]
WINDOW      = 20   # 학습과 동일한 lookback window


class PPOAgent:
    """
    PPO 포트폴리오 에이전트 래퍼
    모델 파일이 없으면 공포탐욕 기반 규칙 배분으로 폴백
    """

    def __init__(self):
        self.model      = None
        self.model_path = settings.MODEL_DIR / settings.PPO_MODEL_FILE
        self.result_path = settings.MODEL_DIR / "training_result.json"
        self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            print(f"PPO 모델 없음: {self.model_path} -> 균등 배분 모드")
            return
        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(str(self.model_path))
            print(f"PPO 모델 로드 완료: {self.model_path}")
        except ImportError:
            print("stable-baselines3 미설치 -> 균등 배분 모드")
        except Exception as e:
            print(f"PPO 로드 오류: {e}")

    def predict(self, market_state: dict) -> dict[str, float]:
        """
        최근 20일 실제 주가 데이터로 관측 벡터 구성 → PPO 추론 → 자산 배분
        """
        if self.model is None:
            return self._rule_based_weights(market_state)

        try:
            obs = self._build_observation()
            action, _ = self.model.predict(obs, deterministic=True)
            weights = _softmax(action)
            return {asset: round(float(w), 4) for asset, w in zip(ASSETS, weights)}
        except Exception as e:
            print(f"PPO 추론 오류: {e} -> 규칙 기반 폴백")
            return self._rule_based_weights(market_state)

    def _build_observation(self) -> np.ndarray:
        """
        Yahoo Finance에서 최근 30일 가격 조회 → 20일 수익률 벡터 (120차원) 생성
        """
        end   = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=40)).timestamp())

        price_cols = []
        for sym in SYMBOLS:
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                f"?interval=1d&period1={start}&period2={end}"
            )
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                result = r.json()["chart"]["result"][0]
                closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
                price_cols.append(np.array(closes[-21:], dtype=np.float64))  # 최근 21일
            except Exception:
                price_cols.append(np.ones(21))  # 데이터 없으면 1로 채움

        # 길이 맞추기
        min_len = min(len(c) for c in price_cols)
        prices  = np.column_stack([c[-min_len:] for c in price_cols])  # (min_len, 6)

        if len(prices) < 2:
            return np.zeros(len(SYMBOLS) * WINDOW, dtype=np.float32)

        rets = np.diff(prices, axis=0) / (prices[:-1] + 1e-8)  # (min_len-1, 6)

        # 마지막 WINDOW행만 사용, 부족하면 앞을 0으로 패딩
        if len(rets) >= WINDOW:
            rets = rets[-WINDOW:]
        else:
            pad  = WINDOW - len(rets)
            rets = np.vstack([np.zeros((pad, len(SYMBOLS))), rets])

        return np.clip(rets.flatten(), -0.15, 0.15).astype(np.float32)

    def backtest(self, days: int = 30) -> dict:
        """
        training_result.json에서 실제 백테스트 결과를 읽어 반환
        """
        if self.result_path.exists():
            data = json.loads(self.result_path.read_text(encoding="utf-8"))
            bt   = data.get("backtest", {})
            return {
                "period_days": data.get("test_days", days),
                "trained_at":  data.get("trained_at", ""),
                "train_days":  data.get("train_days", 0),
                "ppo": {
                    "return":   bt.get("ppo_return", 0),
                    "sharpe":   bt.get("sharpe", 0),
                    "max_dd":   bt.get("max_dd", 0),
                    "win_rate": bt.get("win_rate", 0),
                },
                "buy_and_hold": {
                    "return":   bt.get("bnh_return", 0),
                    "sharpe":   None,
                    "max_dd":   None,
                    "win_rate": None,
                },
                "avg_weights": data.get("avg_weights", {}),
                "assets":      data.get("assets", []),
            }

        # 결과 파일 없으면 더미
        return {
            "period_days": days,
            "ppo":          {"return": 0, "sharpe": 0, "max_dd": 0, "win_rate": 0},
            "buy_and_hold": {"return": 0, "sharpe": None, "max_dd": None, "win_rate": None},
        }

    def _rule_based_weights(self, market_state: dict) -> dict[str, float]:
        fng = market_state.get("fng", 50)
        if fng < 30:
            return {"BTC": 0.10, "ETH": 0.05, "SOL": 0.05,
                    "AAPL": 0.15, "NVDA": 0.10, "TSLA": 0.05, "CASH": 0.50}
        elif fng < 50:
            return {"BTC": 0.15, "ETH": 0.10, "SOL": 0.05,
                    "AAPL": 0.20, "NVDA": 0.15, "TSLA": 0.05, "CASH": 0.30}
        elif fng < 70:
            return {"BTC": 0.20, "ETH": 0.15, "SOL": 0.10,
                    "AAPL": 0.20, "NVDA": 0.20, "TSLA": 0.05, "CASH": 0.10}
        else:
            return {"BTC": 0.25, "ETH": 0.20, "SOL": 0.10,
                    "AAPL": 0.20, "NVDA": 0.20, "TSLA": 0.05, "CASH": 0.00}


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()
