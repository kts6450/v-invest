/**
 * PipelineStatus - AI 분석 파이프라인 진행 상황 표시 컴포넌트
 *
 * [역할]
 *   - "AI 분석 실행" 버튼 클릭 → POST /analysis/run
 *   - EventSource('/analysis/stream') → 진행 상황 실시간 수신
 *   - 각 단계별 상태를 시각적 + TTS로 안내 (시각 장애인 UX)
 *   - 완료 시 onComplete(report) 콜백으로 최신 리포트 전달
 *
 * [Props]
 *   onComplete(report) : 파이프라인 완료 시 리포트 전달
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// 단계별 한국어 라벨 + 예상 소요시간
const STEP_INFO = {
  collecting:  { label: "시장 데이터 수집",    icon: "📡", est: 15 },
  integrating: { label: "데이터 통합·검증",    icon: "🔄", est: 2  },
  processing:  { label: "기술적 지표 계산",    icon: "📊", est: 2  },
  scoring:     { label: "시장 심리 점수",      icon: "🎯", est: 1  },
  analyst:     { label: "투자분석가 AI",       icon: "🤖", est: 20 },
  risk:        { label: "리스크 전문가 AI",    icon: "🛡️", est: 15 },
  editor:      { label: "편집장 자기검증",     icon: "✏️", est: 15 },
  evaluating:  { label: "리포트 품질 평가",   icon: "📋", est: 2  },
  rag:         { label: "RAG 과거 리포트 참조", icon: "📚", est: 5  },
  formatting:  { label: "최종 리포트 작성",   icon: "📝", est: 2  },
  saving:      { label: "저장 중",            icon: "💾", est: 1  },
  done:        { label: "완료",               icon: "✅", est: 0  },
  error:       { label: "오류",               icon: "❌", est: 0  },
};

const STEP_ORDER = [
  "collecting", "integrating", "processing", "scoring",
  "analyst", "risk", "editor", "evaluating", "rag", "formatting", "saving", "done",
];

export default function PipelineStatus({ onComplete }) {
  const { speak } = useTextToSpeech();
  const [isRunning,    setIsRunning]    = useState(false);
  const [currentStep,  setCurrentStep]  = useState(null);
  const [completedSteps, setCompleted]  = useState([]);
  const [lastMessage,  setLastMessage]  = useState("");
  const [elapsedSec,   setElapsed]      = useState(0);

  const eventSourceRef = useRef(null);
  const timerRef       = useRef(null);

  // 경과 시간 타이머
  useEffect(() => {
    if (isRunning) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isRunning]);

  // SSE 파이프라인 스트림 구독
  const subscribeToStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${API_BASE}/analysis/stream`);

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        const { step, message, report } = event;

        setCurrentStep(step);
        setLastMessage(message);

        if (step !== "done" && step !== "error") {
          setCompleted((prev) => {
            const idx = STEP_ORDER.indexOf(step);
            return STEP_ORDER.slice(0, idx);
          });
        }

        // 중요 단계만 TTS 알림 (너무 많으면 시각 장애인 사용자에게 부담)
        const voiceSteps = ["scoring", "analyst", "risk", "done", "error"];
        if (voiceSteps.includes(step)) {
          speak(message);
        }

        if (step === "done") {
          setIsRunning(false);
          setCompleted(STEP_ORDER.slice(0, -1));
          if (report) onComplete?.(report);
        }

        if (step === "error") {
          setIsRunning(false);
          speak(`오류가 발생했습니다. ${message}`);
        }
      } catch {}
    };

    es.onerror = () => {
      // SSE 연결 끊기면 재연결 (keepalive timeout은 무시)
    };

    eventSourceRef.current = es;
  }, [speak, onComplete]);

  useEffect(() => {
    subscribeToStream();
    return () => eventSourceRef.current?.close();
  }, [subscribeToStream]);

  // 분석 실행 버튼 클릭
  const handleRun = async () => {
    if (isRunning) return;

    try {
      const res  = await fetch(`${API_BASE}/analysis/run`, { method: "POST" });
      const data = await res.json();

      if (data.status === "already_running") {
        speak("파이프라인이 이미 실행 중입니다.");
        return;
      }

      setIsRunning(true);
      setCompleted([]);
      setCurrentStep("collecting");
      speak("AI 투자 분석을 시작합니다. 데이터 수집부터 시작합니다.");
    } catch {
      speak("파이프라인 실행에 실패했습니다. 서버 연결을 확인해 주세요.");
    }
  };

  const currentInfo = STEP_INFO[currentStep] || {};
  const progress    = currentStep
    ? Math.round((STEP_ORDER.indexOf(currentStep) / (STEP_ORDER.length - 1)) * 100)
    : 0;

  return (
    <section
      aria-label="AI 투자 분석 파이프라인"
      className="rounded-2xl p-4 border border-gray-700"
      style={{ background: "#111827" }}
    >
      {/* 제목 + 실행 버튼 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-bold text-base" style={{ color: "#FFD700" }}>
            🤖 AI 멀티에이전트 분석
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            투자분석가 → 리스크 전문가 → 편집장
          </p>
        </div>

        <button
          onClick={handleRun}
          disabled={isRunning}
          aria-label={isRunning ? `분석 중... ${elapsedSec}초 경과` : "AI 투자 분석 지금 실행"}
          className="
            px-4 py-2 rounded-xl font-bold text-sm
            transition-all active:scale-95
            focus:outline-none focus:ring-2 focus:ring-yellow-400
            disabled:opacity-60
          "
          style={{
            background: isRunning ? "#374151" : "#f59e0b",
            color:      isRunning ? "#9ca3af" : "#000",
          }}
        >
          {isRunning ? `⏳ ${elapsedSec}s` : "▶ 분석 실행"}
        </button>
      </div>

      {/* 진행 바 */}
      {isRunning && (
        <div className="mb-3">
          <div
            className="h-1.5 rounded-full mb-1"
            style={{ background: "#1f2937" }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`분석 진행률 ${progress}%`}
          >
            <div
              className="h-1.5 rounded-full transition-all duration-1000"
              style={{ width: `${progress}%`, background: "#f59e0b" }}
            />
          </div>
          <p className="text-xs text-gray-400">{progress}% 완료</p>
        </div>
      )}

      {/* 현재 단계 */}
      {currentStep && (
        <div
          aria-live="polite"
          aria-atomic="true"
          className="flex items-center gap-2 p-3 rounded-xl mb-3"
          style={{ background: "#1f2937" }}
        >
          <span aria-hidden="true" className="text-xl">{currentInfo.icon}</span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-white">
              {currentInfo.label}
            </p>
            <p className="text-xs text-gray-400">{lastMessage}</p>
          </div>
          {isRunning && currentStep !== "done" && (
            <div aria-hidden="true" className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-yellow-400"
                  style={{ animation: `bounce 0.6s ${i * 0.2}s infinite` }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* 완료된 단계 목록 (체크리스트 형태) */}
      {completedSteps.length > 0 && (
        <ul
          role="list"
          aria-label="완료된 분석 단계"
          className="space-y-1"
        >
          {completedSteps.map((step) => {
            const info = STEP_INFO[step] || {};
            return (
              <li
                key={step}
                role="listitem"
                className="flex items-center gap-2 text-xs text-gray-500"
              >
                <span className="text-green-400">✓</span>
                <span>{info.label}</span>
              </li>
            );
          })}
        </ul>
      )}

      {/* 완료 메시지 */}
      {currentStep === "done" && (
        <p
          className="text-sm font-bold mt-2"
          style={{ color: "#00FF88" }}
          aria-label="분석 완료. 새 리포트를 확인하세요."
        >
          ✅ 분석 완료! 새 리포트를 확인하세요.
        </p>
      )}
    </section>
  );
}
