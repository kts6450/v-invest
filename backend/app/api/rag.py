"""
RAG 투자 Q&A 라우터

[흐름]
  사용자 음성 질문 (STT로 변환된 텍스트)
      → ChromaDB에서 유사 리포트 검색
      → GPT-4o-mini에 컨텍스트 주입
      → 답변 텍스트 반환 (TTS로 바로 읽어줌)

[시각 장애인 최적화]
  - 답변은 300자 이내 (음성으로 1분 이내 청취)
  - 수치는 반드시 단위 포함 ("52달러" not "$52")
  - 문장 부호 최소화 (TTS 자연스러운 읽기)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag_service import get_rag_chain

router = APIRouter()


class ChatRequest(BaseModel):
    question:  str
    user_id:   str  = "anonymous"
    use_rag:   bool = True         # False = 순수 LLM (RAG 비활성)
    tts_ready: bool = True         # True = TTS 최적화 형식으로 답변


class ChatResponse(BaseModel):
    answer:           str          # TTS로 읽어줄 답변
    sources:          list[dict]   # 참조된 리포트 메타데이터
    retrieved_chunks: int


@router.post("/chat", response_model=ChatResponse,
             summary="RAG 기반 투자 Q&A (음성 질문 처리)")
async def chat(req: ChatRequest):
    """
    STT로 변환된 텍스트 질문 수신 → RAG 답변 → TTS 반환

    [연동 흐름]
      1. 프론트엔드: 마이크 녹음 → POST /voice/stt → 텍스트
      2. 프론트엔드: 텍스트 → POST /rag/chat → 답변
      3. 프론트엔드: 답변 → POST /voice/tts → 음성 재생
    """
    if not req.question.strip():
        raise HTTPException(400, "질문이 비어 있습니다")

    try:
        rag_chain = await get_rag_chain()

        if req.use_rag:
            result = rag_chain.query(req.question, top_k=5)
        else:
            result = rag_chain.query_without_rag(req.question)

        answer = result["answer"]

        # TTS 최적화: 달러 기호 → 한국어 단위 변환
        if req.tts_ready:
            answer = _tts_optimize(answer)

        return ChatResponse(
            answer=answer,
            sources=result.get("sources", []),
            retrieved_chunks=result.get("retrieved_chunks", 0),
        )
    except Exception as e:
        raise HTTPException(500, f"RAG 오류: {str(e)}")


@router.post("/add-report", summary="새 리포트를 벡터 DB에 추가 (n8n에서 자동 호출)")
async def add_report(content: str, source: str = "n8n", date: str = ""):
    """
    n8n 멀티에이전트가 생성한 리포트를 ChromaDB에 저장
    → 다음 RAG 질문 시 참조 문서로 활용
    """
    rag_chain = await get_rag_chain()
    n_chunks  = rag_chain.kb.add_report(content, "daily_report", date, source)
    return {"status": "saved", "chunks": n_chunks}


def _tts_optimize(text: str) -> str:
    """
    TTS 자연스러운 읽기를 위한 텍스트 전처리
    특수 문자 → 음성 친화적 표현으로 변환
    """
    replacements = {
        "$":  "달러 ",
        "%":  "퍼센트",
        "+":  "플러스 ",
        "✅": "",
        "⚠️": "주의. ",
        "🔴": "",
        "🟢": "",
        "▲":  "상승 ",
        "▼":  "하락 ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
