"""
PPO 포트폴리오 최적화 모델 학습 스크립트

[실행 방법]
  cd v-invest/backend
  python train_ppo.py

[학습 결과]
  models/ppo_portfolio.zip 저장 → 서버 재시작하면 자동 로드

[소요 시간]
  CPU: 약 5~10분
  M1/M2 Mac: 약 2~3분
"""
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

MODEL_DIR  = Path(__file__).parent / "models"
MODEL_FILE = MODEL_DIR / "ppo_portfolio.zip"
MODEL_DIR.mkdir(exist_ok=True)

# ── 학습용 더미 가격 데이터 생성 (실제 데이터 없을 시) ──
def generate_price_data(n_days: int = 365, n_assets: int = 6) -> np.ndarray:
    """
    BTC, ETH, SOL, AAPL, NVDA, TSLA 6개 자산의 일별 가격 시뮬레이션
    GBM(기하 브라운 운동) 모델 사용
    """
    np.random.seed(42)
    # 각 자산의 연간 기대 수익률 및 변동성
    returns = np.array([0.80, 0.60, 1.20, 0.25, 0.60, 0.40])  # 연간 수익률
    vols    = np.array([0.70, 0.75, 1.00, 0.30, 0.55, 0.65])  # 연간 변동성

    dt = 1 / 252
    prices = np.ones((n_days, n_assets)) * 100.0

    for t in range(1, n_days):
        z = np.random.standard_normal(n_assets)
        prices[t] = prices[t-1] * np.exp(
            (returns - 0.5 * vols**2) * dt + vols * np.sqrt(dt) * z
        )
    return prices


# ── Gymnasium 커스텀 환경 ──
class PortfolioEnv:
    """
    PPO 학습용 포트폴리오 환경 (Gymnasium 호환)
    """

    def __init__(self, price_data: np.ndarray, window: int = 10):
        self.data     = price_data
        self.n_assets = price_data.shape[1]
        self.window   = window
        self.t        = window

        # Gymnasium 호환 속성
        import gymnasium as gym
        self.observation_space = gym.spaces.Box(
            low=-1, high=1,
            shape=(self.n_assets * window,),
            dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=-1, high=1,
            shape=(self.n_assets + 1,),  # +1 for CASH
            dtype=np.float32
        )

    def reset(self, seed=None):
        self.t = self.window
        return self._get_obs(), {}

    def step(self, action):
        weights = self._softmax(action)

        # 포트폴리오 수익률 계산
        if self.t < len(self.data) - 1:
            day_returns = self.data[self.t + 1] / self.data[self.t] - 1
            port_return = float(np.dot(weights[:-1], day_returns))
        else:
            port_return = 0.0

        # 보상: 샤프 비율 근사
        std    = max(float(np.std(day_returns if self.t < len(self.data) - 1 else [0])), 1e-6)
        reward = port_return / std

        self.t += 1
        done = self.t >= len(self.data) - 2

        return self._get_obs(), reward, done, False, {}

    def _get_obs(self) -> np.ndarray:
        start = max(0, self.t - self.window)
        window_data = self.data[start:self.t]
        if len(window_data) < 2:
            return np.zeros(self.n_assets * self.window, dtype=np.float32)
        returns = np.diff(window_data, axis=0) / (window_data[:-1] + 1e-8)
        # 부족한 길이 패딩
        pad = self.window - 1 - len(returns)
        if pad > 0:
            returns = np.vstack([np.zeros((pad, self.n_assets)), returns])
        obs = np.clip(returns.flatten(), -0.15, 0.15).astype(np.float32)
        return obs

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - x.max())
        return e / e.sum()


def train():
    print("=" * 50)
    print("🚀 PPO 포트폴리오 모델 학습 시작")
    print("=" * 50)

    # ── 1. 가격 데이터 준비 ──
    print("\n📊 학습 데이터 생성 중...")
    price_data = generate_price_data(n_days=500, n_assets=6)
    print(f"   데이터 형태: {price_data.shape} (500일 × 6개 자산)")

    # ── 2. 환경 생성 ──
    env = PortfolioEnv(price_data)

    # ── 3. PPO 학습 ──
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env
        from stable_baselines3.common.vec_env import DummyVecEnv

        print("\n🤖 PPO 모델 학습 중... (약 3~5분 소요)")
        vec_env = DummyVecEnv([lambda: PortfolioEnv(price_data)])
        model   = PPO(
            "MlpPolicy",
            vec_env,
            verbose=1,
            learning_rate=3e-4,
            n_steps=256,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            tensorboard_log=None,
        )
        model.learn(total_timesteps=50_000)

        # ── 4. 모델 저장 ──
        model.save(str(MODEL_FILE).replace(".zip", ""))
        print(f"\n✅ 모델 저장 완료: {MODEL_FILE}")

    except ImportError:
        print("\n⚠️  stable-baselines3 미설치")
        print("   pip install stable-baselines3 gymnasium 후 다시 실행하세요")
        return

    # ── 5. 간단 백테스트 ──
    print("\n📈 백테스트 실행 중...")
    obs, _  = env.reset()
    total_r = 0
    steps   = 0
    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, _, _ = env.step(action)
        total_r += reward
        steps   += 1
        if done:
            break

    print(f"   학습 완료: {steps}스텝 | 누적 보상: {total_r:.2f}")
    print(f"\n🎉 서버를 재시작하면 PPO 모델이 자동으로 로드됩니다")
    print(f"   uvicorn app.main:app --reload --port 8001")


if __name__ == "__main__":
    train()
