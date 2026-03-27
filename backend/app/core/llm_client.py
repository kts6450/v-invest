"""
LLM 클라이언트 팩토리
OpenAI (GPT-4o Vision, Whisper, TTS) 및 Gemini 클라이언트를 생성·반환

[사용처]
  charts.py  → get_vision_client()  : 차트 이미지 분석
  voice.py   → get_openai_client()  : Whisper STT / TTS
  rag.py     → get_chat_client()    : RAG 대화
"""
from openai import AsyncOpenAI
import google.genai as genai
from app.core.config import settings

# ── 싱글턴 클라이언트 (모듈 로드 시 1회 초기화) ──
_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """OpenAI 비동기 클라이언트 반환 (싱글턴)"""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def get_vision_client() -> AsyncOpenAI:
    """GPT-4o Vision 용 클라이언트 (get_openai_client와 동일, 명시적 alias)"""
    return get_openai_client()


def get_gemini_client():
    """
    Gemini Vision 클라이언트 (OpenAI 실패 시 fallback)
    사용: google.generativeai.GenerativeModel("gemini-2.5-flash")
    """
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    return genai.GenerativeModel("gemini-2.5-flash")


def get_chat_client() -> AsyncOpenAI:
    """RAG 대화용 경량 모델 클라이언트"""
    return get_openai_client()
