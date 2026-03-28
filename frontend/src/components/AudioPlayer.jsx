import { useEffect, useRef, useState } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";
import { Play, Square, Volume2 } from "lucide-react";

export default function AudioPlayer({ text, autoPlay = false, useOpenAI = false, title = "음성 재생" }) {
  const { speak, stop, isSpeaking } = useTextToSpeech({ useOpenAI });
  const containerRef = useRef(null);

  useEffect(() => {
    if (autoPlay && text) speak(text);
    return () => stop();
  }, [text, autoPlay]); // eslint-disable-line

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onKey = (e) => {
      if (e.code === "Space") { e.preventDefault(); isSpeaking ? stop() : speak(text); }
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [isSpeaking, text, speak, stop]);

  return (
    <section ref={containerRef} role="region" aria-label={title} tabIndex={0}
      className="flex items-center gap-3 focus:outline-none"
      style={{ userSelect: "none" }}>
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {isSpeaking ? `${title} 재생 중` : `${title} 정지`}
      </div>

      <button onClick={() => isSpeaking ? stop() : speak(text)}
        aria-label={isSpeaking ? "정지" : "재생"}
        className="w-8 h-8 rounded-lg flex items-center justify-center transition-all focus:outline-none flex-shrink-0"
        style={{
          background: isSpeaking ? "rgba(239,68,68,0.15)" : "rgba(99,102,241,0.12)",
          border: isSpeaking ? "1px solid rgba(239,68,68,0.25)" : "1px solid rgba(99,102,241,0.2)",
        }}>
        {isSpeaking
          ? <Square size={12} color="#ef4444" />
          : <Play size={12} color="#818cf8" />
        }
      </button>

      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        <Volume2 size={11} style={{ color: isSpeaking ? "#818cf8" : "var(--text-muted)", flexShrink: 0 }} />
        <p className="text-xs truncate" style={{ color: isSpeaking ? "var(--text-secondary)" : "var(--text-muted)" }}>
          {isSpeaking ? "재생 중..." : (title || text?.slice(0, 40))}
        </p>
        {isSpeaking && (
          <div className="flex items-end gap-0.5 flex-shrink-0" aria-hidden="true">
            {[1,2,3].map(i => (
              <div key={i} className="w-0.5 rounded-full animate-pulse-dot"
                style={{ background: "#818cf8", height: `${6 + i * 3}px`, animationDelay: `${i * 0.1}s` }} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
