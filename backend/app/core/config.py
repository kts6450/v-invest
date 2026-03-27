"""
환경 변수 및 전역 설정
모든 API 키, 경로, 파라미터를 한 곳에서 관리
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── API Keys ──
    OPENAI_API_KEY:  str = ""   # GPT-4o Vision + Whisper STT + TTS
    GOOGLE_API_KEY:  str = ""   # Gemini Vision (fallback)
    FINNHUB_API_KEY: str = ""   # 주식 실시간 시세
    FRED_API_KEY:    str = ""   # 매크로 지표

    # ── 경로 ──
    BASE_DIR:    Path = Path(__file__).parent.parent.parent
    CHROMA_DIR:  Path = BASE_DIR / "chroma_db"   # 벡터 DB 저장 경로
    MODEL_DIR:   Path = BASE_DIR / "models"      # PPO 모델 파일 경로

    # ── LLM 파라미터 ──
    VISION_MODEL:  str = "gpt-4o"          # 차트 이미지 분석용 (고성능)
    CHAT_MODEL:    str = "gpt-4o-mini"     # RAG 대화용 (경량·저비용)
    TTS_MODEL:     str = "tts-1"           # OpenAI TTS
    TTS_VOICE:     str = "nova"            # nova = 부드럽고 명확한 여성 목소리
    STT_MODEL:     str = "whisper-1"       # OpenAI Whisper STT
    EMBED_MODEL:   str = "text-embedding-3-small"

    # ── PPO 파라미터 ──
    PPO_MODEL_FILE: str = "ppo_portfolio.zip"
    ASSETS:         list = ["BTC", "ETH", "SOL", "AAPL", "NVDA", "TSLA", "CASH"]

    # ── Binance WebSocket ──
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"
    CRYPTO_SYMBOLS: list = ["btcusdt", "ethusdt", "solusdt"]

    class Config:
        env_file = ".env"
        extra    = "ignore"


settings = Settings()
