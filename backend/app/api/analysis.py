"""
AI 투자 분석 파이프라인 API 라우터

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
발표 주제 대응
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① ML API를 Web Server 통해 서비스
   → 이 파일의 모든 엔드포인트가 "ML API"
   → FastAPI가 투자분석가·리스크·편집장 AI, RAG, PPO를 REST API로 제공

② n8n에 연결해서 ML API 활용한 서비스
   → n8n HTTP Request 노드가 아래 엔드포인트를 호출
   → POST /analysis/run-sync  (n8n이 완료될 때까지 대기 후 리포트 수신)
   → GET  /analysis/latest    (n8n이 결과 조회 후 웹UI 저장)

[n8n 연동 플로우]
  n8n 스케줄 트리거 (1시간)
      ↓
  POST /analysis/run-sync   ← n8n HTTP Request 노드 (timeout: 180s)
      ↓  (FastAPI 내부에서 데이터수집→AI분석→RAG→저장 전부 처리)
  리포트 JSON 반환
      ↓
  n8n Code 노드 (sentimentScore, grade 추출)
      ↓
  POST /reports/save  or  Discord Webhook (선택)

[프론트엔드 연동]
  POST /analysis/run    → 백그라운드 실행 (즉시 반환)
  GET  /analysis/stream → SSE 진행 상황 실시간 수신
  GET  /analysis/latest → 최신 리포트 조회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.services.analysis_pipeline import (
    run_pipeline,
    get_report_history,
    get_pipeline_status,
    pipeline_event_stream,
)

router = APIRouter()


# ══════════════════════════════════════════
# n8n 전용 엔드포인트 (동기 실행 - n8n이 결과를 기다림)
# ══════════════════════════════════════════

@router.post("/run-sync", summary="【n8n 전용】ML API 동기 실행 - 완료까지 대기 후 리포트 반환")
async def run_analysis_sync():
    """
    n8n HTTP Request 노드에서 호출하는 ML API 엔드포인트

    [n8n 설정]
      Method : POST
      URL    : http://127.0.0.1:8000/analysis/run-sync
      Timeout: 180000 (3분 - AI 3개 에이전트 실행 시간 고려)

    [반환값]
      리포트 전체 JSON (n8n Code 노드에서 $json.sentimentScore 등으로 접근)

    [발표 시 포인트]
      "n8n이 FastAPI의 ML API를 호출해서 AI 분석 결과를 받아옵니다"
      → ML API 서비스 + n8n 연동 두 요구사항 동시 충족
    """
    status = get_pipeline_status()
    if status["is_running"]:
        # 이미 실행 중이면 완료될 때까지 폴링 후 반환
        for _ in range(60):   # 최대 60초 대기
            await asyncio.sleep(2)
            if not get_pipeline_status()["is_running"]:
                break
        reports = get_report_history(limit=1)
        if reports:
            return reports[-1]
        raise HTTPException(503, "파이프라인 실행 중이나 결과를 가져올 수 없습니다")

    result = await run_pipeline(triggered_by="n8n")
    if result.get("status") != "ok":
        raise HTTPException(500, f"파이프라인 실패: {result}")
    return result.get("report", {})


@router.post("/run", summary="AI 투자 분석 파이프라인 즉시 실행")
async def run_analysis(background_tasks: BackgroundTasks):
    """
    n8n 웹훅 트리거 대체 — 클릭 한 번으로 전체 파이프라인 실행

    [실행 순서]
    시장 데이터 수집 → 심리점수 → 투자분석가 AI → 리스크 AI → 편집장 AI → 저장

    [반환]
    바로 {"status": "started"} 반환 후 백그라운드 실행
    진행 상황은 GET /analysis/stream 으로 실시간 확인
    """
    status = get_pipeline_status()
    if status["is_running"]:
        return {"status": "already_running", "message": "파이프라인이 이미 실행 중입니다. /analysis/stream 으로 진행 상황을 확인하세요."}

    # 백그라운드 실행 (요청 즉시 반환)
    background_tasks.add_task(_run_in_background)
    return {"status": "started", "message": "파이프라인 실행 시작. /analysis/stream 에서 진행 상황을 확인하세요."}


@router.get("/status", summary="파이프라인 실행 상태 확인")
async def pipeline_status():
    """
    현재 파이프라인 실행 여부 + 마지막 실행 정보

    [프론트엔드 폴링 예시]
      setInterval(() => fetch('/analysis/status').then(r=>r.json()).then(setStatus), 5000)
    """
    return get_pipeline_status()


@router.get("/stream", summary="SSE - 파이프라인 진행 상황 실시간 스트리밍")
async def analysis_stream():
    """
    Server-Sent Events로 파이프라인 각 단계 진행 상황을 실시간 전달

    [이벤트 step 목록]
      collecting  → 시장 데이터 수집 중
      integrating → 데이터 통합 중
      processing  → 기술적 지표 계산 중
      scoring     → 심리 점수 산출 완료
      analyst     → 투자분석가 AI 작성 중
      risk        → 리스크 전문가 AI 검토 중
      editor      → 편집장 AI 자기검증 중
      evaluating  → 품질 평가 중
      rag         → RAG 과거 리포트 참조 중
      formatting  → 최종 리포트 작성 중
      saving      → 저장 중
      done        → 완료 (report 필드에 리포트 미리보기 포함)
      error       → 오류 발생
      warning     → 데이터 품질 경고

    [프론트엔드 사용법]
      const es = new EventSource('/analysis/stream');
      es.onmessage = (e) => {
        const event = JSON.parse(e.data);
        updateProgress(event.step, event.message);
        if (event.step === 'done') loadLatestReport();
      };
    """
    return StreamingResponse(
        pipeline_event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history", summary="AI 투자 리포트 히스토리 조회")
async def report_history(limit: int = 10):
    """
    저장된 리포트 목록 반환 (최신 순)
    프론트엔드 히스토리 페이지, 대시보드 카드 등에 사용
    """
    reports = get_report_history(limit=limit)
    return {
        "total":   len(reports),
        "reports": [_summarize(r) for r in reversed(reports)],
    }


@router.get("/latest", summary="최신 AI 투자 리포트 조회")
async def latest_report():
    """
    가장 최근 완료된 리포트 전체 내용 반환
    대시보드 메인 화면에서 사용
    """
    reports = get_report_history(limit=1)
    if not reports:
        raise HTTPException(404, "아직 실행된 리포트가 없습니다. POST /analysis/run 으로 먼저 실행하세요.")
    return reports[-1]


# ══════════════════════════════════════════
# n8n 또는 외부에서 리포트 저장 (하위 호환)
# ══════════════════════════════════════════

@router.post("/save", summary="리포트 외부 저장 (n8n 워크플로우 호환)")
async def save_report_external(report: dict):
    """
    n8n 워크플로우의 '웹UI 리포트 저장' 노드 호환 엔드포인트
    POST http://127.0.0.1:8000/reports/save 도 동일하게 라우팅

    n8n이 ML API 결과를 통합한 뒤 최종 저장할 때 호출
    """
    from app.services.analysis_pipeline import save_report
    await save_report(report)
    return {"status": "saved", "date": report.get("date")}


# ── 헬퍼 ──

async def _run_in_background():
    """백그라운드 태스크로 파이프라인 실행"""
    try:
        await run_pipeline(triggered_by="api")
    except Exception as e:
        print(f"❌ 파이프라인 백그라운드 실행 오류: {e}")


def _summarize(report: dict) -> dict:
    """히스토리 목록용 요약 (전체 분석 텍스트 제외)"""
    return {
        "date":           report.get("date"),
        "sentimentScore": report.get("sentimentScore"),
        "sentimentLabel": report.get("sentimentLabel"),
        "grade":          (report.get("quality") or {}).get("grade"),
        "qualityScore":   (report.get("quality") or {}).get("score"),
        "summary":        report.get("summary", "")[:500],
    }
