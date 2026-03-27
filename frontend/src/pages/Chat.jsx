/**
 * Chat - 음성 기반 RAG 투자 Q&A 페이지
 *
 * [사용 흐름]
 *   1. 화면 아무 곳이나 길게 누름 → 마이크 활성화
 *   2. 질문 발화 (예: "지금 비트코인 사도 돼?")
 *   3. Whisper STT 또는 Web Speech API로 텍스트 변환
 *   4. /rag/chat으로 POST → AI 답변 수신
 *   5. 답변 자동 TTS 재생
 *
 * [접근성]
 *   - 메시지 버블에 role="article" + aria-label (발화자 + 내용)
 *   - 새 메시지 도착 시 aria-live="polite"로 스크린 리더 알림
 *   - 긴 텍스트는 AudioPlayer 컴포넌트로 재생 버튼 제공
 */
import { useState, useRef, useEffect } from "react";
import VoiceInput from "../components/VoiceInput";
import AudioPlayer from "../components/AudioPlayer";
import { useTextToSpeech } from "../hooks/useTextToSpeech";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Chat() {
  const { speak } = useTextToSpeech();
  const [messages,   setMessages]   = useState([
    { role: "assistant", text: "안녕하세요. 투자에 관해 궁금한 것을 음성으로 질문해 주세요.", id: 0 },
  ]);
  const [isLoading,  setIsLoading]  = useState(false);
  const bottomRef = useRef(null);

  // 새 메시지 도착 시 스크롤 + TTS
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && messages.length > 1) {
      speak(last.text);
    }
  }, [messages]); // eslint-disable-line

  // ── 음성 질문 처리 ──
  const handleVoiceSubmit = async (question) => {
    if (!question.trim() || isLoading) return;

    // 사용자 메시지 추가
    const userMsg = { role: "user", text: question, id: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/rag/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question, tts_ready: true }),
      });
      const data = await res.json();
      const aiMsg = {
        role:    "assistant",
        text:    data.answer,
        sources: data.sources || [],
        id:      Date.now() + 1,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "오류가 발생했습니다. 다시 시도해 주세요.", id: Date.now() + 1 },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main
      className="min-h-screen flex flex-col pb-40"
      style={{ background: "#0a0a0f", color: "#fff" }}
    >
      {/* 헤더 */}
      <header className="sticky top-0 px-4 py-3 border-b border-gray-800 z-10" style={{ background: "#0a0a0f" }}>
        <h1 className="text-lg font-bold" style={{ color: "#FFD700" }}>
          💬 AI 투자 상담
        </h1>
        <p className="text-xs text-gray-500">RAG 기반 · 금융 리포트 참조</p>
      </header>

      {/* 메시지 목록 */}
      <div
        role="log"
        aria-label="대화 내용"
        aria-live="polite"
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      >
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {/* 로딩 인디케이터 */}
        {isLoading && (
          <div aria-label="AI가 답변을 생성하고 있습니다" className="flex gap-1 p-3">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="w-2 h-2 rounded-full bg-blue-400"
                style={{ animation: `bounce 0.8s ${i * 0.2}s infinite` }}
              />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 고정 하단: 음성 입력 */}
      <div
        className="fixed bottom-0 left-0 right-0 p-4 border-t border-gray-800"
        style={{ background: "#0d1117" }}
      >
        <VoiceInput
          onSubmit={handleVoiceSubmit}
          placeholder="화면을 길게 누르고 질문하세요"
        />
      </div>
    </main>
  );
}


// ── 메시지 버블 컴포넌트 ──
function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <article
      aria-label={`${isUser ? "사용자" : "AI 어시스턴트"}: ${msg.text}`}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className="max-w-xs lg:max-w-md rounded-2xl px-4 py-3"
        style={{
          background: isUser ? "#1d4ed8" : "#1f2937",
          borderRadius: isUser ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
        }}
      >
        <p className="text-sm leading-relaxed text-white" aria-hidden="true">
          {msg.text}
        </p>

        {/* AI 답변 재생 버튼 (긴 텍스트) */}
        {!isUser && msg.text.length > 50 && (
          <div className="mt-2">
            <AudioPlayer text={msg.text} title="AI 답변 듣기" />
          </div>
        )}

        {/* 참조 문서 */}
        {msg.sources?.length > 0 && (
          <details className="mt-2 text-xs text-gray-400">
            <summary className="cursor-pointer">참조 {msg.sources.length}건</summary>
            {msg.sources.map((s, i) => (
              <p key={i}>{s.metadata?.source} · {s.metadata?.date}</p>
            ))}
          </details>
        )}
      </div>
    </article>
  );
}
