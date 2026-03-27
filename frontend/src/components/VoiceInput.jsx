/**
 * VoiceInput - 시각 장애인 최적화 음성 입력 컴포넌트
 *
 * [UX 설계]
 *   - 화면 전체를 터치하면 녹음 시작 (작은 버튼 찾을 필요 없음)
 *   - 손을 떼면 자동 인식 및 전송
 *   - 녹음 중 진동(100ms) + 실시간 음성파형 시각화
 *   - ARIA live region으로 스크린 리더에 상태 즉시 전달
 *
 * [Props]
 *   onSubmit(text: string) → 인식 완료된 텍스트 전달
 *   placeholder            → 안내 멘트 (TTS로 읽어줌)
 *   fullScreen             → true면 화면 전체가 터치 영역
 */
import { useEffect, useRef } from "react";
import { useSpeechToText } from "../hooks/useSpeechToText";
import { useTextToSpeech } from "../hooks/useTextToSpeech";

export default function VoiceInput({
  onSubmit,
  placeholder = "화면을 누르고 말씀하세요",
  fullScreen  = false,
}) {
  const { speak } = useTextToSpeech();
  const { transcript, interimText, isListening, startListening, stopListening, error } =
    useSpeechToText({ onResult: onSubmit });

  const canvasRef = useRef(null);
  const animRef   = useRef(null);

  // 컴포넌트 마운트 시 안내 음성 재생
  useEffect(() => {
    speak(placeholder);
  }, []); // eslint-disable-line

  // 에러 발생 시 음성 안내
  useEffect(() => {
    if (error) speak("음성 인식에 실패했습니다. 다시 시도해 주세요.");
  }, [error]); // eslint-disable-line

  // 음성파형 애니메이션 (녹음 중에만 표시)
  useEffect(() => {
    if (!isListening) {
      cancelAnimationFrame(animRef.current);
      _clearCanvas(canvasRef.current);
      return;
    }
    _drawWaveform(canvasRef.current, animRef);
    return () => cancelAnimationFrame(animRef.current);
  }, [isListening]);

  const containerClass = fullScreen
    ? "fixed inset-0 flex flex-col items-center justify-center z-50"
    : "flex flex-col items-center gap-4 p-4";

  return (
    <div
      className={containerClass}
      style={{ background: isListening ? "rgba(0,0,0,0.85)" : "transparent" }}
    >
      {/* ARIA live: 스크린 리더에 상태 실시간 전달 */}
      <div
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {isListening
          ? "녹음 중입니다. 말씀을 마치신 후 손을 떼세요."
          : transcript
          ? `인식된 내용: ${transcript}`
          : ""}
      </div>

      {/* 메인 마이크 버튼 (전체 터치 or 버튼) */}
      <button
        aria-label={isListening ? "녹음 중. 손을 떼면 전송됩니다" : placeholder}
        aria-pressed={isListening}
        onPointerDown={startListening}
        onPointerUp={stopListening}
        onPointerLeave={stopListening}
        className="
          relative w-32 h-32 rounded-full
          flex items-center justify-center
          text-5xl select-none
          transition-all duration-200
          focus:outline-none focus:ring-4 focus:ring-yellow-400
        "
        style={{
          background:  isListening
            ? "radial-gradient(circle, #e74c3c, #c0392b)"
            : "radial-gradient(circle, #3498db, #2980b9)",
          boxShadow: isListening
            ? "0 0 40px rgba(231, 76, 60, 0.8)"
            : "0 8px 30px rgba(52, 152, 219, 0.5)",
          transform: isListening ? "scale(1.15)" : "scale(1)",
        }}
      >
        {isListening ? "🔴" : "🎤"}
      </button>

      {/* 음성파형 (시각적 피드백) */}
      <canvas
        ref={canvasRef}
        width={280}
        height={60}
        aria-hidden="true"
        style={{ display: isListening ? "block" : "none" }}
        className="rounded-lg opacity-80"
      />

      {/* 상태 텍스트 */}
      <p
        className="text-center font-semibold text-lg"
        style={{
          color:  isListening ? "#e74c3c" : "#ecf0f1",
          minHeight: "2rem",
        }}
      >
        {isListening
          ? interimText || "듣고 있어요..."
          : transcript
          ? `"${transcript}"`
          : placeholder}
      </p>
    </div>
  );
}


// ── 음성파형 캔버스 애니메이션 ──
function _drawWaveform(canvas, animRef) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;

  function frame(t) {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#e74c3c";
    ctx.lineWidth   = 2;
    ctx.beginPath();

    for (let x = 0; x < W; x++) {
      const freq   = 3 + Math.sin(t / 1000) * 2;
      const amp    = 15 + Math.random() * 10;
      const y      = H / 2 + Math.sin((x / W) * Math.PI * freq + t / 200) * amp;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    animRef.current = requestAnimationFrame(frame);
  }

  animRef.current = requestAnimationFrame(frame);
}

function _clearCanvas(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}
