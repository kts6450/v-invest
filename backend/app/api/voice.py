"""
Voice 인터페이스 라우터 - STT(음성→텍스트) / TTS(텍스트→음성)

[흐름]
  STT: 프론트엔드 마이크 녹음 → WAV/WebM blob → Whisper API → 텍스트
  TTS: 텍스트(AI 분석 결과 등) → OpenAI TTS → MP3 스트리밍 → 프론트엔드 재생

[시각 장애인 UX 고려사항]
  - TTS 응답은 즉각적이어야 함 (스트리밍 방식 채택)
  - STT는 언어 자동 감지 (한국어 우선)
  - 에러 시에도 음성으로 피드백 ("인식하지 못했습니다. 다시 말씀해 주세요.")
"""
import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.llm_client import get_openai_client
from app.core.config import settings

router = APIRouter()


# ────────────────────────────────
# STT: 음성 → 텍스트
# ────────────────────────────────

@router.post("/stt", summary="음성 파일 → 텍스트 변환 (Whisper)")
async def speech_to_text(
    audio: UploadFile = File(..., description="WAV / WebM / MP3 오디오 파일"),
):
    """
    Web Speech API 미지원 환경 또는 높은 정확도 필요 시 사용
    프론트엔드에서 MediaRecorder로 녹음한 WebM blob 수신
    → OpenAI Whisper API → 텍스트 반환
    """
    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(400, "오디오 데이터가 너무 짧습니다")

    client = get_openai_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = audio.filename or "audio.webm"

    try:
        transcript = await client.audio.transcriptions.create(
            model=settings.STT_MODEL,
            file=audio_file,
            language="ko",                 # 한국어 우선 인식
            response_format="json",
        )
        return {
            "text":     transcript.text,
            "language": "ko",
            "model":    settings.STT_MODEL,
        }
    except Exception as e:
        raise HTTPException(500, f"STT 오류: {str(e)}")


# ────────────────────────────────
# TTS: 텍스트 → 음성
# ────────────────────────────────

class TTSRequest(BaseModel):
    text:  str            # 읽어줄 텍스트
    voice: str = "nova"   # nova(여성·부드러움), alloy, echo, fable, onyx, shimmer
    speed: float = 1.0    # 1.0 = 기본, 0.8 = 느리게 (노인·청각 약자 배려)


@router.post("/tts", summary="텍스트 → 음성 MP3 스트리밍")
async def text_to_speech(req: TTSRequest):
    """
    AI 분석 결과 또는 차트 설명을 즉시 음성으로 변환
    StreamingResponse로 반환 → 프론트엔드 <audio> 태그에서 즉시 재생

    [프론트엔드 사용법]
      const res = await fetch('/voice/tts', { method: 'POST', body: JSON.stringify({text}) });
      const audioUrl = URL.createObjectURL(await res.blob());
      new Audio(audioUrl).play();
    """
    if not req.text.strip():
        raise HTTPException(400, "텍스트가 비어 있습니다")

    client = get_openai_client()
    try:
        # 텍스트 길이 제한 (TTS API: 4096자)
        text = req.text[:4000]
        response = await client.audio.speech.create(
            model=settings.TTS_MODEL,
            voice=req.voice,
            input=text,
            speed=req.speed,
            response_format="mp3",
        )
        audio_bytes = response.content

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3"},
        )
    except Exception as e:
        raise HTTPException(500, f"TTS 오류: {str(e)}")


@router.post("/tts/error-feedback", summary="에러 시 음성 피드백 생성")
async def error_feedback(message: str = "오류가 발생했습니다. 다시 시도해 주세요."):
    """
    시각 장애인 UX: 에러 상황을 음성으로 즉시 안내
    UI 시각 피드백이 보이지 않으므로 음성 피드백이 필수
    """
    req = TTSRequest(text=message, voice="nova", speed=0.9)
    return await text_to_speech(req)
