"""
V-Invest Backend - FastAPI Root
시각 장애인을 위한 Voice-Vision AI 투자 어시스턴트

[아키텍처 흐름]
  프론트엔드(React PWA)
      │
      ├─ POST /voice/stt            → 음성 → 텍스트 (Whisper)
      ├─ POST /voice/tts            → 텍스트 → 음성 (OpenAI TTS)
      ├─ POST /charts/analyze       → 차트 이미지 → 음성 설명 텍스트 (GPT-4o Vision)
      ├─ POST /rag/chat             → RAG 기반 투자 Q&A
      ├─ GET  /portfolio/recommend  → PPO 포트폴리오 추천
      ├─ POST /analysis/run         → AI 투자 분석 파이프라인 즉시 실행 (n8n 대체)
      ├─ GET  /analysis/stream      → SSE 파이프라인 진행 상황 실시간 스트리밍
      ├─ GET  /analysis/history     → 리포트 히스토리 조회
      └─ GET  /analysis/latest      → 최신 리포트 조회

[스케줄링]
  APScheduler가 1시간마다 자동으로 run_pipeline() 실행 (n8n 스케줄 트리거 대체)
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api import charts, voice, portfolio, rag, n8n, analysis
from app.core.config import settings
from app.services.rag_service import init_rag
from app.services.analysis_pipeline import run_pipeline

# ── APScheduler (n8n 스케줄 트리거 대체) ──
scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행되는 라이프사이클 훅"""
    # ── 시작 ──
    print("🚀 V-Invest 서버 시작")
    await init_rag()   # ChromaDB + LangChain RAG 초기화

    # APScheduler: 1시간마다 자동 파이프라인 실행 (n8n 스케줄 트리거 대체)
    scheduler.add_job(
        _scheduled_pipeline,
        trigger="interval",
        hours=1,
        id="auto_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    print("⏰ APScheduler 시작 (1시간마다 자동 분석)")

    yield

    # ── 종료 ──
    scheduler.shutdown(wait=False)
    print("🛑 V-Invest 서버 종료")


async def _scheduled_pipeline():
    """APScheduler 콜백 (n8n 스케줄 트리거 대체)"""
    print("⏰ 정기 자동 분석 시작...")
    try:
        await run_pipeline(triggered_by="schedule")
    except Exception as e:
        print(f"❌ 정기 분석 오류: {e}")


app = FastAPI(
    title="V-Invest API",
    description="시각 장애인 전용 Voice-Vision AI 투자 어시스턴트 (n8n 불필요)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ──
app.include_router(voice.router,     prefix="/voice",     tags=["🎤 Voice STT/TTS"])
app.include_router(charts.router,    prefix="/charts",    tags=["📊 Vision 차트 분석"])
app.include_router(rag.router,       prefix="/rag",       tags=["📚 RAG 투자 Q&A"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["💼 PPO 포트폴리오"])
app.include_router(analysis.router,  prefix="/analysis",  tags=["🤖 AI 분석 파이프라인"])
app.include_router(n8n.router,       prefix="/n8n",       tags=["🔌 n8n 연동 (선택)"])


@app.post("/reports/save", tags=["📄 리포트 저장 (n8n 호환)"],
          summary="n8n 워크플로우 호환 리포트 저장 엔드포인트")
async def save_report_compat(report: dict):
    """
    기존 n8n 워크플로우의 'POST /reports/save' 노드와 호환
    /analysis/save 와 동일한 동작
    """
    from app.services.analysis_pipeline import save_report
    await save_report(report)
    return {"status": "saved", "date": report.get("date")}


@app.get("/health")
async def health():
    return {
        "status":    "ok",
        "service":   "V-Invest API v2.0",
        "scheduler": scheduler.running,
        "next_run":  str(scheduler.get_job("auto_pipeline").next_run_time) if scheduler.get_job("auto_pipeline") else None,
    }
