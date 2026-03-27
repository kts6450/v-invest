/**
 * App.js - V-Invest 루트 컴포넌트
 *
 * [네비게이션 구조]
 *   하단 탭바 (3개): 대시보드 / 채팅 / 포트폴리오
 *   - 탭 전환 시 TTS로 페이지 이름 읽어줌 (시각 장애인 UX)
 *   - 활성 탭에 aria-current="page" 적용
 *
 * [PWA]
 *   - manifest.json: 홈 화면 추가, 전체화면 모드
 *   - service-worker: 오프라인 캐싱
 */
import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Chat      from "./pages/Chat";
import Portfolio from "./pages/Portfolio";
import { useTextToSpeech } from "./hooks/useTextToSpeech";

const TABS = [
  { id: "dashboard", label: "대시보드", emoji: "📊", Component: Dashboard },
  { id: "chat",      label: "AI 상담",  emoji: "💬", Component: Chat      },
  { id: "portfolio", label: "포트폴리오", emoji: "💼", Component: Portfolio },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const { speak } = useTextToSpeech();

  const handleTabChange = (tab) => {
    setActiveTab(tab.id);
    speak(`${tab.label} 페이지로 이동합니다.`);
  };

  const ActivePage = TABS.find((t) => t.id === activeTab)?.Component ?? Dashboard;

  return (
    <div
      className="max-w-md mx-auto min-h-screen relative"
      style={{ fontFamily: "'Noto Sans KR', sans-serif" }}
    >
      {/* 스킵 내비게이션 (스크린 리더용) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 bg-yellow-400 text-black px-4 py-2 z-50"
      >
        본문으로 바로가기
      </a>

      {/* 페이지 컨텐츠 */}
      <div id="main-content">
        <ActivePage />
      </div>

      {/* 하단 탭 네비게이션 */}
      <nav
        role="navigation"
        aria-label="주요 메뉴"
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md
                   border-t border-gray-800 flex"
        style={{ background: "#0d1117" }}
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab)}
              aria-label={tab.label}
              aria-current={isActive ? "page" : undefined}
              className="
                flex-1 flex flex-col items-center py-3 gap-1
                transition-colors focus:outline-none focus:bg-gray-800
              "
              style={{ color: isActive ? "#FFD700" : "#6b7280" }}
            >
              <span aria-hidden="true" className="text-xl">{tab.emoji}</span>
              <span className="text-xs font-medium">{tab.label}</span>
              {isActive && (
                <span
                  className="absolute top-0 h-0.5 w-16 rounded-full"
                  style={{ background: "#FFD700" }}
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* 전역 CSS (고대비 모드, 애니메이션) */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;900&display=swap');

        /* 접근성: 사용자 모션 감소 설정 존중 */
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after { animation: none !important; transition: none !important; }
        }

        /* 포커스 가시성 강화 (고대비) */
        :focus-visible { outline: 3px solid #FFD700 !important; outline-offset: 2px; }

        /* 스크린 리더 전용 숨김 클래스 */
        .sr-only {
          position: absolute; width: 1px; height: 1px;
          padding: 0; margin: -1px; overflow: hidden;
          clip: rect(0,0,0,0); border: 0;
        }
        .sr-only.focus\\:not-sr-only:focus {
          position: static; width: auto; height: auto;
          padding: inherit; margin: inherit; overflow: visible;
          clip: auto;
        }

        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50%       { transform: translateY(-6px); }
        }
        @keyframes pulse {
          from { opacity: 0.5; }
          to   { opacity: 1.0; }
        }
      `}</style>
    </div>
  );
}
