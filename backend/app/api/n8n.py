"""
n8n 멀티에이전트 연동 라우터

[역할]
  n8n 워크플로우(투자분석가 + 리스크 전문가 + 편집장 AI)가
  분석을 완료하면 이 엔드포인트로 결과를 POST 전송
  → RAG 벡터 DB에 저장 (다음 질문 시 참조)
  → 프론트엔드 실시간 푸시 (SSE 또는 WebSocket)
  → TTS용 요약 텍스트 생성

[n8n에서의 호출]
  HTTP Request 노드:
    POST http://localhost:8000/n8n/report
    Body: { content, sentimentScore, grade, ... }
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from typing import AsyncGenerator

from app.services.rag_service import get_rag_chain

router = APIRouter()

# ── SSE(Server-Sent Events)로 실시간 리포트 푸시 ──
_report_queue: asyncio.Queue = asyncio.Queue(maxsize=10)


class N8nReportRequest(BaseModel):
    """n8n 워크플로우에서 전송하는 리포트 데이터"""
    content:        str
    sentimentScore: int   = 0
    sentimentLabel: str   = ""
    grade:          str   = ""
    score:          int   = 0


class N8nReportResponse(BaseModel):
    status:       str
    report_id:    int
    voice_summary: str   # TTS로 읽어줄 요약


@router.post("/report", response_model=N8nReportResponse,
             summary="n8n 멀티에이전트 리포트 수신 및 저장")
async def receive_report(
    req: N8nReportRequest,
    background_tasks: BackgroundTasks,
):
    """
    n8n → 여기로 POST → RAG 저장 + SSE 브로드캐스트

    [처리 순서]
    1. 리포트를 RAG ChromaDB에 저장 (향후 질문 시 참조)
    2. SSE 큐에 넣어 프론트엔드로 실시간 알림
    3. TTS 요약 텍스트 생성하여 반환
    """
    now = datetime.now()

    # 1. RAG에 저장 (백그라운드)
    background_tasks.add_task(_save_to_rag, req.content, now.strftime("%Y-%m-%d"))

    # 2. SSE 큐에 push (프론트엔드 실시간 알림)
    report_data = {
        "type":           "new_report",
        "timestamp":      now.isoformat(),
        "sentimentScore": req.sentimentScore,
        "sentimentLabel": req.sentimentLabel,
        "grade":          req.grade,
        "preview":        req.content[:200],
    }
    if not _report_queue.full():
        await _report_queue.put(report_data)

    # 3. TTS 요약 생성
    voice_summary = (
        f"새 AI 투자 리포트가 도착했습니다. "
        f"시장 심리 점수 {req.sentimentScore}점, {req.sentimentLabel}. "
        f"리포트 등급 {req.grade}. "
        f"자세한 내용을 들으시려면 화면을 터치하세요."
    )

    return N8nReportResponse(
        status="saved",
        report_id=now.microsecond % 10000,
        voice_summary=voice_summary,
    )


@router.get("/stream", summary="SSE - 새 리포트 실시간 스트리밍")
async def stream_reports():
    """
    Server-Sent Events로 프론트엔드에 새 리포트 도착 알림
    시각 장애인: 새 리포트 도착 시 자동으로 TTS 알림 재생

    [프론트엔드 사용법]
      const es = new EventSource('/n8n/stream');
      es.onmessage = (e) => {
        const report = JSON.parse(e.data);
        speakText(report.voice_summary);  // 자동 TTS 알림
      };
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                data = await asyncio.wait_for(_report_queue.get(), timeout=30)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"   # 연결 유지용 ping

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _save_to_rag(content: str, date: str):
    """백그라운드: 리포트를 RAG 벡터 DB에 저장"""
    try:
        rag = await get_rag_chain()
        rag.kb.add_report(content, "n8n_report", date, "n8n")
    except Exception as e:
        print(f"RAG 저장 실패: {e}")
