/**
 * AudioPlayer - 접근성 최적화 오디오 플레이어
 *
 * [용도]
 *   AI 분석 결과, 차트 설명, 포트폴리오 추천 등을
 *   자동 재생하거나 수동으로 제어하는 컴포넌트
 *
 * [접근성]
 *   - 키보드: Space(재생/정지), ArrowRight/Left(10초 이동), +/-(속도)
 *   - ARIA: role="region" + aria-label로 스크린 리더 정확히 안내
 *   - 재생 상태를 aria-live로 실시간 알림
 *
 * [Props]
 *   text          : TTS로 읽어줄 텍스트
 *   autoPlay      : true면 컴포넌트 마운트 시 자동 재생
 *   useOpenAI     : true면 OpenAI TTS, false면 Web Speech API
 *   title         : 접근성 라벨 (예: "차트 분석 결과")
 */
import { useEffect, useRef, useState } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";

export default function AudioPlayer({
  text,
  autoPlay   = false,
  useOpenAI  = false,
  title      = "음성 재생",
}) {
  const { speak, stop, pause, resume, isSpeaking } = useTextToSpeech({ useOpenAI });
  const [speed, setSpeed]   = useState(1.0);
  const [isPaused, setPaused] = useState(false);
  const containerRef = useRef(null);

  // 자동 재생
  useEffect(() => {
    if (autoPlay && text) speak(text);
    return () => stop();
  }, [text, autoPlay]); // eslint-disable-line

  // 키보드 단축키
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    function onKey(e) {
      if (e.code === "Space") {
        e.preventDefault();
        isSpeaking ? (isPaused ? resume() : pause()) : speak(text);
        setPaused((p) => !p);
      }
      if (e.code === "KeyS") stop();
    }
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [isSpeaking, isPaused, text, speak, stop, pause, resume]);

  const handlePlay = () => {
    if (isSpeaking) {
      stop();
    } else {
      speak(text);
      setPaused(false);
    }
  };

  return (
    <section
      ref={containerRef}
      role="region"
      aria-label={title}
      tabIndex={0}
      className="
        bg-gray-900 border border-gray-700 rounded-2xl p-4
        focus:outline-none focus:ring-2 focus:ring-blue-400
      "
      style={{ userSelect: "none" }}
    >
      {/* ARIA live: 재생 상태 알림 */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {isSpeaking ? `${title} 재생 중` : `${title} 정지`}
      </div>

      {/* 제목 */}
      <h3 className="text-sm text-gray-400 mb-3 font-medium">{title}</h3>

      {/* 텍스트 미리보기 */}
      <p
        className="text-white text-sm leading-relaxed mb-4 line-clamp-3"
        aria-hidden="true"
      >
        {text || "재생할 내용이 없습니다."}
      </p>

      {/* 컨트롤 버튼 */}
      <div className="flex items-center gap-3" role="toolbar" aria-label="재생 컨트롤">
        {/* 재생/정지 */}
        <button
          onClick={handlePlay}
          aria-label={isSpeaking ? "정지 (S키)" : "재생 (스페이스키)"}
          className="
            w-12 h-12 rounded-full flex items-center justify-center text-xl
            transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400
          "
          style={{
            background: isSpeaking ? "#e74c3c" : "#3498db",
          }}
        >
          {isSpeaking ? "⏹" : "▶"}
        </button>

        {/* 속도 조절 */}
        <div className="flex items-center gap-2" aria-label="재생 속도">
          {[0.8, 1.0, 1.25, 1.5].map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              aria-label={`재생 속도 ${s}배`}
              aria-pressed={speed === s}
              className="
                px-2 py-1 rounded text-xs font-bold
                focus:outline-none focus:ring-2 focus:ring-yellow-400
                transition-colors
              "
              style={{
                background: speed === s ? "#f39c12" : "#2c3e50",
                color:      speed === s ? "#000"    : "#ecf0f1",
              }}
            >
              {s}×
            </button>
          ))}
        </div>

        {/* 재생 인디케이터 */}
        {isSpeaking && (
          <div aria-hidden="true" className="flex items-center gap-1 ml-auto">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="w-1 rounded-full bg-blue-400"
                style={{
                  height:    `${8 + i * 4}px`,
                  animation: `pulse ${0.4 + i * 0.1}s ease-in-out infinite alternate`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 키보드 단축키 안내 */}
      <p className="text-xs text-gray-600 mt-3" aria-label="키보드 단축키">
        스페이스: 재생/정지 · S: 중지
      </p>
    </section>
  );
}
