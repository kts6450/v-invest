import { useState, useRef, useEffect } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";
import {
  Bot, User, Send, Mic, MicOff, Volume2,
  Sparkles, FileText, BookOpen, TrendingUp,
  ChevronDown, Hash, Lightbulb,
} from "lucide-react";
import { useSpeechToText } from "../hooks/useSpeechToText";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const QUICK = [
  { label: "비트코인 전망",  q: "현재 비트코인 시장 전망과 투자 시점을 알려줘" },
  { label: "NVDA 리스크",   q: "NVIDIA 주식의 주요 리스크 요인은 무엇인가요?" },
  { label: "인플레이션",     q: "현재 인플레이션 상황과 포트폴리오 영향을 분석해줘" },
  { label: "금리 영향",      q: "금리 인상이 내 포트폴리오에 미치는 영향은?" },
  { label: "분산 투자",      q: "현재 시장에서 최적의 자산 분산 전략을 알려줘" },
  { label: "섹터 분석",      q: "AI 반도체 섹터 투자 기회와 리스크를 분석해줘" },
];

const DOCS = [
  { title: "2024 Q4 시장 분석 리포트", date: "2024-12-15", tag: "매크로" },
  { title: "AI 반도체 섹터 딥다이브",  date: "2024-11-28", tag: "섹터"  },
  { title: "암호화폐 규제 동향 분석",   date: "2024-11-10", tag: "크립토" },
];

export default function Chat() {
  const { speak }   = useTextToSpeech();
  const [messages,  setMessages]  = useState([
    { role: "assistant", text: "안녕하세요! 투자에 관한 궁금한 점을 질문해 주세요.\n\nRAG 기반으로 금융 리포트를 참조해 정확한 분석을 제공합니다. 음성 입력도 지원합니다.", id: 0 },
  ]);
  const [input,     setInput]     = useState("");
  const [loading,   setLoading]   = useState(false);
  const [showDocs,  setShowDocs]  = useState(false);
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);

  const { isListening, startListening, stopListening, transcript } = useSpeechToText({
    onResult: (text) => { setInput(text); },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && messages.length > 1) speak(last.text);
  }, [messages]); // eslint-disable-line

  const submit = async (q) => {
    const text = (q ?? input).trim();
    if (!text || loading) return;
    setInput("");
    setMessages(p => [...p, { role: "user", text, id: Date.now() }]);
    setLoading(true);
    try {
      const res  = await fetch(`${API_BASE}/rag/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, tts_ready: true }),
      });
      const data = await res.json();
      setMessages(p => [...p, { role: "assistant", text: data.answer, sources: data.sources || [], id: Date.now() + 1 }]);
    } catch {
      setMessages(p => [...p, { role: "assistant", text: "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", id: Date.now() + 1 }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full" style={{ height: "calc(100vh - 56px)" }}>

      {/* ── 좌측: 채팅 영역 ── */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* 채팅 헤더 */}
        <div className="flex-shrink-0 px-6 py-4"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-primary)" }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
                <Sparkles size={15} color="#fff" />
              </div>
              <div>
                <h1 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>AI 투자 상담</h1>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>RAG · GPT-4o-mini · 금융 리포트 기반</p>
              </div>
            </div>
            <button
              onClick={() => setShowDocs(p => !p)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors focus:outline-none"
              style={{ background: showDocs ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.04)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              <BookOpen size={12} />
              참조 문서
            </button>
          </div>
        </div>

        {/* 메시지 영역 */}
        <div
          role="log"
          aria-label="대화 내용"
          aria-live="polite"
          className="flex-1 overflow-y-auto px-6 py-5 space-y-5"
          style={{ background: "var(--bg-primary)" }}
        >
          {/* 빠른 질문 칩 */}
          {messages.length < 2 && (
            <div className="mb-2">
              <p className="text-xs font-semibold mb-3 flex items-center gap-1.5"
                style={{ color: "var(--text-muted)" }}>
                <Lightbulb size={11} /> 추천 질문
              </p>
              <div className="flex flex-wrap gap-2">
                {QUICK.map((item) => (
                  <button key={item.label}
                    onClick={() => submit(item.q)}
                    className="text-xs px-3 py-1.5 rounded-full font-medium transition-all focus:outline-none active:scale-95"
                    style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", color: "#818cf8" }}>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => <Bubble key={msg.id} msg={msg} speak={speak} />)}

          {loading && (
            <div className="flex items-end gap-2.5">
              <div className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
                <Bot size={13} color="#fff" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-sm flex items-center gap-2"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
                    style={{ background: "#6366f1", animationDelay: `${i * 0.15}s` }} />
                ))}
                <span className="text-xs ml-1" style={{ color: "var(--text-muted)" }}>분석 중...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* 입력 영역 */}
        <div className="flex-shrink-0 px-6 py-4"
          style={{ borderTop: "1px solid var(--border)", background: "rgba(8,11,20,0.95)" }}>

          {/* 음성 인식 중 표시 */}
          {isListening && (
            <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-xl animate-fade-in"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
              <div className="w-2 h-2 rounded-full" style={{ background: "#ef4444", boxShadow: "0 0 6px #ef4444" }} />
              <span className="text-xs" style={{ color: "#ef4444" }}>
                {transcript || "듣고 있어요..."}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2">
            <div
              className="flex-1 flex items-center gap-3 px-4 py-3 rounded-2xl"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <Hash size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && submit()}
                placeholder="투자 질문을 입력하세요... (Enter로 전송)"
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: "var(--text-primary)" }}
                aria-label="메시지 입력"
              />
            </div>

            {/* 음성 버튼 */}
            <button
              onPointerDown={startListening}
              onPointerUp={stopListening}
              onPointerLeave={stopListening}
              className="w-11 h-11 rounded-xl flex items-center justify-center transition-all focus:outline-none flex-shrink-0"
              style={{
                background: isListening ? "rgba(239,68,68,0.15)" : "rgba(255,255,255,0.05)",
                border: isListening ? "1px solid rgba(239,68,68,0.3)" : "1px solid var(--border)",
              }}
              aria-label={isListening ? "녹음 중 - 손 떼면 전송" : "음성 입력"}
              aria-pressed={isListening}
            >
              {isListening
                ? <MicOff size={16} color="#ef4444" />
                : <Mic size={16} style={{ color: "var(--text-muted)" }} />
              }
            </button>

            {/* 전송 */}
            <button
              onClick={() => submit()}
              disabled={!input.trim() || loading}
              className="w-11 h-11 rounded-xl flex items-center justify-center transition-all disabled:opacity-30 focus:outline-none flex-shrink-0"
              style={{ background: input.trim() ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "rgba(255,255,255,0.05)", border: "1px solid var(--border)" }}
              aria-label="전송"
            >
              <Send size={15} color={input.trim() ? "#fff" : "var(--text-muted)"} />
            </button>
          </div>
        </div>
      </div>

      {/* ── 우측: 참조 문서 패널 ── */}
      {showDocs && (
        <div className="w-72 flex-shrink-0 flex flex-col animate-fade-in"
          style={{ borderLeft: "1px solid var(--border)", background: "var(--bg-secondary)" }}>
          <div className="px-4 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>참조 문서 DB</h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>ChromaDB · {DOCS.length}개 문서</p>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {DOCS.map((doc, i) => (
              <div key={i} className="p-3 rounded-xl card-hover cursor-pointer"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <div className="flex items-start gap-2 mb-1.5">
                  <FileText size={12} style={{ color: "var(--text-muted)", marginTop: 1, flexShrink: 0 }} />
                  <p className="text-xs font-medium leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {doc.title}
                  </p>
                </div>
                <div className="flex items-center gap-2 pl-5">
                  <span className="text-xs px-1.5 py-0.5 rounded font-medium"
                    style={{ background: "rgba(99,102,241,0.1)", color: "#818cf8" }}>
                    {doc.tag}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{doc.date}</span>
                </div>
              </div>
            ))}
          </div>

          {/* 문서 추가 안내 */}
          <div className="p-4" style={{ borderTop: "1px solid var(--border)" }}>
            <div className="p-3 rounded-xl text-center"
              style={{ background: "rgba(99,102,241,0.06)", border: "1px dashed rgba(99,102,241,0.2)" }}>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                POST /rag/add-report 로<br/>문서를 추가할 수 있습니다
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Bubble({ msg, speak }) {
  const isUser = msg.role === "user";
  const [open, setOpen] = useState(false);

  return (
    <article
      aria-label={`${isUser ? "사용자" : "AI 어시스턴트"}: ${msg.text}`}
      className={`flex items-end gap-2.5 animate-fade-in ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 mb-0.5"
          style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} aria-hidden="true">
          <Bot size={13} color="#fff" />
        </div>
      )}

      <div className="max-w-lg space-y-1.5">
        <div
          className="px-4 py-3"
          style={{
            background: isUser ? "linear-gradient(135deg,#4f46e5,#7c3aed)" : "var(--bg-card)",
            border: isUser ? "none" : "1px solid var(--border)",
            borderRadius: isUser ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
          }}
        >
          <p className="text-sm leading-relaxed whitespace-pre-line"
            style={{ color: isUser ? "#fff" : "var(--text-primary)" }} aria-hidden="true">
            {msg.text}
          </p>
        </div>

        {!isUser && msg.text.length > 60 && (
          <button
            onClick={() => speak(msg.text)}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors focus:outline-none ml-1"
            style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)", color: "#818cf8" }}>
            <Volume2 size={11} /> 음성으로 듣기
          </button>
        )}

        {!isUser && msg.sources?.length > 0 && (
          <>
            <button onClick={() => setOpen(p => !p)}
              className="flex items-center gap-1.5 text-xs ml-1 focus:outline-none transition-colors"
              style={{ color: "var(--text-muted)" }}>
              <FileText size={11} />
              참조 문서 {msg.sources.length}건
              <ChevronDown size={11} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            </button>
            {open && (
              <div className="ml-1 p-3 rounded-xl space-y-1 animate-fade-in"
                style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                {msg.sources.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: "#6366f1" }} />
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {s.metadata?.source}{s.metadata?.date ? ` · ${s.metadata.date}` : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 mb-0.5"
          style={{ background: "rgba(99,102,241,0.15)" }} aria-hidden="true">
          <User size={13} style={{ color: "#818cf8" }} />
        </div>
      )}
    </article>
  );
}
