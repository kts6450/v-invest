"""
PPO 포트폴리오 최적화 모델 학습 스크립트
Yahoo Finance에서 실제 과거 주가 데이터를 가져와 학습합니다.

[실행]
  cd backend
  .\\venv\\Scripts\\python train_ppo.py

[결과]
  models/ppo_portfolio.zip 저장 → 서버 재시작 시 자동 로드
"""
import numpy as np
import pandas as pd
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

MODEL_DIR  = Path(__file__).parent / "models"
MODEL_FILE = MODEL_DIR / "ppo_portfolio.zip"
MODEL_DIR.mkdir(exist_ok=True)

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "NVDA", "TSLA"]
ASSET_NAMES = ["BTC", "ETH", "SOL", "AAPL", "NVDA", "TSLA"]


def fetch_real_prices(lookback_days: int = 730) -> np.ndarray:
    """
    Yahoo Finance에서 실제 과거 2년 일봉 종가 데이터 수집
    """
    print("  Yahoo Finance에서 실제 주가 데이터 수집 중...")
    end   = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=lookback_days)).timestamp())

    all_prices = []
    for sym in ASSETS:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
            f"?interval=1d&period1={start}&period2={end}"
        )
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
            result = r.json()["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            all_prices.append(closes)
            print(f"    {sym}: {len(closes)}일 데이터 수집")
        except Exception as e:
            print(f"    {sym}: 수집 실패 ({e}) → GBM 시뮬레이션으로 대체")
            all_prices.append(None)

    # 길이 맞추기 (가장 짧은 기간 기준)
    valid   = [p for p in all_prices if p is not None]
    min_len = min(len(p) for p in valid) if valid else 365

    price_matrix = []
    for i, prices in enumerate(all_prices):
        if prices is None:
            # 수집 실패한 자산은 GBM 시뮬레이션
            sim = _gbm_simulate(min_len)
            price_matrix.append(sim)
        else:
            price_matrix.append(np.array(prices[-min_len:]))

    data = np.column_stack(price_matrix)
    print(f"\n  실제 데이터 shape: {data.shape}  ({data.shape[0]}일 x {data.shape[1]}개 자산)")
    return data


def _gbm_simulate(n_days: int, mu: float = 0.3, sigma: float = 0.6) -> np.ndarray:
    np.random.seed(42)
    dt     = 1 / 252
    prices = [100.0]
    for _ in range(n_days - 1):
        z = np.random.standard_normal()
        prices.append(prices[-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z))
    return np.array(prices)


# ── Gymnasium 커스텀 환경 ──
import gymnasium as gym

class PortfolioEnv(gym.Env):
    """
    PPO 학습용 포트폴리오 환경 (gymnasium.Env 정식 상속)

    State  : 최근 window일 수익률 벡터 (n_assets * window)
    Action : 각 자산 투자 비중 로짓 (softmax → 비중 합계 1.0)
    Reward : 일일 포트폴리오 샤프 비율 (수익 / 변동성)
    """
    metadata = {"render_modes": []}

    def __init__(self, price_data: np.ndarray, window: int = 20):
        super().__init__()
        self.data     = price_data
        self.n_assets = price_data.shape[1]
        self.window   = window
        self.t        = window

        self.observation_space = gym.spaces.Box(
            low=-1, high=1,
            shape=(self.n_assets * window,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=-1, high=1,
            shape=(self.n_assets + 1,),   # +1 = CASH
            dtype=np.float32,
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.t = self.window
        return self._obs(), {}

    def step(self, action):
        weights = _softmax(action)
        if self.t < len(self.data) - 1:
            day_ret  = self.data[self.t + 1] / self.data[self.t] - 1
            port_ret = float(np.dot(weights[:-1], day_ret))
        else:
            port_ret = 0.0
            day_ret  = np.zeros(self.n_assets)

        vol    = max(float(np.std(day_ret)), 1e-6)
        reward = port_ret / vol

        self.t += 1
        done = self.t >= len(self.data) - 2
        return self._obs(), reward, done, False, {}

    def _obs(self) -> np.ndarray:
        start   = max(0, self.t - self.window)
        segment = self.data[start: self.t]
        if len(segment) < 2:
            return np.zeros(self.n_assets * self.window, dtype=np.float32)
        rets = np.diff(segment, axis=0) / (segment[:-1] + 1e-8)
        # window 행으로 패딩 (np.diff로 1행 줄어드므로 pad = window - len(rets))
        pad = self.window - len(rets)
        if pad > 0:
            rets = np.vstack([np.zeros((pad, self.n_assets)), rets])
        return np.clip(rets.flatten(), -0.15, 0.15).astype(np.float32)

    def render(self):
        pass


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def train():
    print("=" * 55)
    print("  PPO 포트폴리오 모델 학습 — 실제 데이터 사용")
    print("=" * 55)

    # ── 1. 실제 주가 데이터 수집 ──
    print("\n[1/4] 실제 주가 데이터 수집")
    price_data = fetch_real_prices(lookback_days=730)

    # 학습용 / 검증용 분리 (80:20)
    split      = int(len(price_data) * 0.8)
    train_data = price_data[:split]
    test_data  = price_data[split:]
    print(f"  학습 기간: {split}일 / 검증 기간: {len(price_data) - split}일")

    # ── 2. 환경 생성 ──
    print("\n[2/4] Gymnasium 환경 생성")
    env = PortfolioEnv(train_data, window=20)
    print(f"  관측 공간: {env.observation_space.shape}")
    print(f"  행동 공간: {env.action_space.shape} ({env.n_assets}개 자산 + CASH)")

    # ── 3. PPO 학습 ──
    print("\n[3/4] PPO 학습 시작 (약 3~5분)")
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv
        from stable_baselines3.common.callbacks import BaseCallback

        class ProgressCallback(BaseCallback):
            def __init__(self, total_steps):
                super().__init__()
                self.total_steps = total_steps
                self.milestones  = set(range(10000, total_steps + 1, 10000))

            def _on_step(self):
                if self.num_timesteps in self.milestones:
                    pct = self.num_timesteps / self.total_steps * 100
                    print(f"  진행: {self.num_timesteps:,} steps ({pct:.0f}%)")
                return True

        TOTAL_STEPS = 100_000
        vec_env = DummyVecEnv([lambda: PortfolioEnv(train_data, window=20)])
        model   = PPO(
            "MlpPolicy",
            vec_env,
            verbose      = 0,
            learning_rate= 3e-4,
            n_steps      = 512,
            batch_size   = 128,
            n_epochs     = 10,
            gamma        = 0.99,
            gae_lambda   = 0.95,
            clip_range   = 0.2,
            ent_coef     = 0.01,
        )
        model.learn(
            total_timesteps = TOTAL_STEPS,
            callback        = ProgressCallback(TOTAL_STEPS),
        )
        model.save(str(MODEL_FILE).replace(".zip", ""))
        print(f"\n  모델 저장: {MODEL_FILE}")

    except ImportError as e:
        print(f"  오류: {e}")
        return

    # ── 4. 검증 백테스트 ──
    print("\n[4/4] 검증 데이터 백테스트")
    test_env = PortfolioEnv(test_data, window=20)
    obs, _   = test_env.reset()

    portfolio_val  = 1.0
    bnh_val        = 1.0
    daily_returns  = []
    weights_log    = []

    while True:
        action, _ = model.predict(obs, deterministic=True)
        weights   = _softmax(action)
        weights_log.append(weights[:-1])

        if test_env.t < len(test_data) - 1:
            day_ret = test_data[test_env.t + 1] / test_data[test_env.t] - 1
            ppo_ret = float(np.dot(weights[:-1], day_ret))
            bnh_ret = float(np.mean(day_ret))
            portfolio_val *= (1 + ppo_ret)
            bnh_val       *= (1 + bnh_ret)
            daily_returns.append(ppo_ret)

        obs, _, done, _, _ = test_env.step(action)
        if done:
            break

    # 성과 지표
    dr = np.array(daily_returns)
    total_ret  = (portfolio_val - 1) * 100
    bnh_ret    = (bnh_val - 1) * 100
    sharpe     = float(np.mean(dr) / np.std(dr) * np.sqrt(252)) if np.std(dr) > 0 else 0
    max_dd     = float(np.min(np.minimum.accumulate(np.cumprod(1 + dr)) - 1) * 100)
    avg_w      = np.mean(weights_log, axis=0)

    print(f"\n  {'=' * 40}")
    print(f"  PPO 전략 수익률   : {total_ret:+.1f}%")
    print(f"  Buy & Hold 수익률 : {bnh_ret:+.1f}%")
    print(f"  샤프 비율          : {sharpe:.2f}")
    print(f"  최대 낙폭(MDD)     : {max_dd:.1f}%")
    print(f"\n  평균 자산 배분:")
    for name, w in zip(ASSET_NAMES, avg_w):
        bar = "█" * int(w * 40)
        print(f"    {name:5s} {w*100:5.1f}%  {bar}")

    # 결과를 JSON으로도 저장
    result = {
        "trained_at": datetime.now().isoformat(),
        "train_days": split,
        "test_days":  len(price_data) - split,
        "assets":     ASSET_NAMES,
        "backtest": {
            "ppo_return":   round(total_ret, 2),
            "bnh_return":   round(bnh_ret, 2),
            "sharpe":       round(sharpe, 2),
            "max_dd":       round(max_dd, 2),
            "win_rate":     round(float(np.mean(dr > 0)), 3),
        },
        "avg_weights": {name: round(float(w), 4) for name, w in zip(ASSET_NAMES, avg_w)},
    }
    result_path = MODEL_DIR / "training_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n  결과 저장: {result_path}")
    print(f"\n  서버 재시작 후 /portfolio/recommend 에서 실제 PPO 추론 확인 가능")


if __name__ == "__main__":
    train()
