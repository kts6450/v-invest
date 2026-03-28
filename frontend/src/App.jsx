import { useState, useEffect, useRef } from "react";
import Dashboard from "./pages/Dashboard";
import Chat      from "./pages/Chat";
import Portfolio from "./pages/Portfolio";
import { useTextToSpeech } from "./hooks/useTextToSpeech";
import {
  LayoutDashboard, MessageCircle, PieChart,
  Activity, TrendingUp, TrendingDown, Wifi,
  Settings, Bell, ChevronLeft, ChevronRight,
  X, BotMessageSquare, Zap,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TABS = [
  { id: "dashboard", label: "대시보드",  Icon: LayoutDashboard, Component: Dashboard },
  { id: "chat",      label: "AI 상담",   Icon: MessageCircle,   Component: Chat      },
  { id: "portfolio", label: "포트폴리오", Icon: PieChart,        Component: Portfolio },
];

const TICKER_ITEMS = [
  { sym: "BTC/USD", price: "—", change: 0, color: "#f59e0b" },
  { sym: "ETH/USD", price: "—", change: 0, color: "#6366f1" },
  { sym: "AAPL",    price: "—", change: 0, color: "#10b981" },
  { sym: "NVDA",    price: "—", change: 0, color: "#8b5cf6" },
  { sym: "TSLA",    price: "—", change: 0, color: "#ef4444" },
  { sym: "S&P 500", price: "—", change: 0, color: "#06b6d4" },
  { sym: "NASDAQ",  price: "—", change: 0, color: "#a78bfa" },
  { sym: "DOW",     price: "—", change: 0, color: "#34d399" },
];

export default function App() {
  const [activeTab,      setActiveTab]      = useState("dashboard");
  const [sidebarOpen,    setSidebarOpen]    = useState(true);
  const [ticker,         setTicker]         = useState(TICKER_ITEMS);
  const [serverStatus,   setServerStatus]   = useState("connecting");
  const [notifications,  setNotifications]  = useState([]);
  const [showNotifPanel, setShowNotifPanel] = useState(false);
  const [n8nToast,       setN8nToast]       = useState(null);
  const [expandedId,     setExpandedId]     = useState(null);
  const sseRef = useRef(null);
  const { speak } = useTextToSpeech();

  // n8n SSE 연결 — /n8n/stream 에서 실시간 리포트 수신
  useEffect(() => {
    const connect = () => {
      if (sseRef.current) sseRef.current.close();
      const es = new EventSource(`${API_BASE}/n8n/stream`);
      sseRef.current = es;

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type !== "new_report") return;

          const notif = {
            id:        Date.now(),
            timestamp: new Date().toLocaleTimeString("ko-KR"),
            sentiment: data.sentimentLabel || "중립",
            score:     data.sentimentScore ?? 50,
            grade:     data.grade || "B",
            content:   data.content || data.preview || "",
            preview:   data.preview || "",
          };

          setNotifications(prev => [notif, ...prev].slice(0, 20));
          setN8nToast(notif);
          setTimeout(() => setN8nToast(null), 7000);

          // 시각장애인: 새 리포트 도착 즉시 TTS 읽기
          speak(
            `n8n AI 리포트 도착. 시장 심리 ${notif.score}점, ${notif.sentiment}. ` +
            `등급 ${notif.grade}.`
          );
        } catch {}
      };

      es.onerror = () => {
        es.close();
        setTimeout(connect, 5000);
      };
    };

    connect();
    return () => sseRef.current?.close();
  }, []);

  // 서버 상태 + 시세 폴링
  useEffect(() => {
    const poll = async () => {
      try {
        await fetch(`${API_BASE}/health`);
        setServerStatus("online");
      } catch {
        setServerStatus("offline");
        return;
      }
      // 티커 업데이트 (market-data + commodities 병렬)
      try {
        const [data, comm] = await Promise.all([
          fetch(`${API_BASE}/market-data`).then(r => r.json()),
          fetch(`${API_BASE}/market-data/commodities`).then(r => r.json()).catch(() => ({})),
        ]);
        const coins  = data?.crypto?.coins || {};
        const stocks = data?.stocks || {};
        const MAP = {
          "BTC/USD": coins.btc,
          "ETH/USD": coins.eth,
          "AAPL":    stocks.aapl,
          "NVDA":    stocks.nvda,
          "TSLA":    stocks.tsla,
          "S&P 500": comm?.sp500,
          "NASDAQ":  comm?.nasdaq,
          "DOW":     comm?.dow,
        };
        setTicker(prev => prev.map(t => {
          const src = MAP[t.sym];
          if (!src) return t;
          const price  = src.usd  ?? src.price;
          const change = src.usd_24h_change ?? src.change ?? 0;
          return { ...t, price: price ? `$${Number(price).toLocaleString()}` : "—", change: change ?? 0 };
        }));
      } catch {}
    };
    poll();
    const iv = setInterval(poll, 30_000);
    return () => clearInterval(iv);
  }, []);

  const handleTabChange = (tab) => {
    if (tab.id === activeTab) return;
    setActiveTab(tab.id);
    speak(`${tab.label} 페이지로 이동합니다.`);
  };

  const ActivePage = TABS.find((t) => t.id === activeTab)?.Component ?? Dashboard;

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "var(--bg-primary)", fontFamily: "'Inter', sans-serif" }}>

      {/* 접근성 스킵 링크 */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1.5 focus:rounded-lg focus:text-xs focus:font-semibold focus:text-black" style={{ background: "#f59e0b" }}>
        본문으로 바로가기
      </a>

      {/* 배경 오브 */}
      <div className="fixed inset-0 pointer-events-none" aria-hidden="true"
        style={{ background: "radial-gradient(ellipse 800px 500px at 30% -50px, rgba(99,102,241,0.08) 0%, transparent 70%)" }} />

      {/* ── 상단 헤더 바 ── */}
      <header
        className="flex-shrink-0 flex items-center h-14 px-4 gap-4 z-30"
        style={{ borderBottom: "1px solid var(--border)", background: "rgba(8,11,20,0.95)", backdropFilter: "blur(20px)" }}
      >
        {/* 로고 */}
        <div className="flex items-center gap-2.5 w-48 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
            <Activity size={14} color="#fff" strokeWidth={2.5} />
          </div>
          <span className="font-bold text-sm gradient-text tracking-tight">V-Invest</span>
          <span className="text-xs px-1.5 py-0.5 rounded font-semibold"
            style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8" }}>Pro</span>
        </div>

        {/* 라이브 티커 */}
        <div className="flex-1 overflow-hidden">
          <div className="flex gap-6 overflow-x-auto scrollbar-hide" style={{ scrollbarWidth: "none" }}>
            {ticker.map((t) => (
              <div key={t.sym} className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>{t.sym}</span>
                <span className="text-xs font-bold" style={{ color: t.color }}>{t.price}</span>
                <span className="text-xs flex items-center gap-0.5"
                  style={{ color: t.change >= 0 ? "#10b981" : "#ef4444" }}>
                  {t.change >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {Math.abs(t.change).toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 우상단 상태 */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full"
              style={{ background: serverStatus === "online" ? "#10b981" : "#ef4444",
                       boxShadow: serverStatus === "online" ? "0 0 6px #10b981" : "none" }} />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {serverStatus === "online" ? "연결됨" : "오프라인"}
            </span>
          </div>
          <Wifi size={14} style={{ color: serverStatus === "online" ? "#10b981" : "var(--text-muted)" }} />
          {/* Bell — n8n 알림 뱃지 */}
          <button
            onClick={() => setShowNotifPanel(p => !p)}
            className="relative focus:outline-none"
            aria-label={`알림 ${notifications.length}개`}
          >
            <Bell size={14} style={{ color: notifications.length > 0 ? "#818cf8" : "var(--text-muted)" }} />
            {notifications.length > 0 && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full text-white flex items-center justify-center"
                style={{ background: "#ef4444", fontSize: "8px", fontWeight: 700 }}>
                {notifications.length > 9 ? "9+" : notifications.length}
              </span>
            )}
          </button>
          <Settings size={14} style={{ color: "var(--text-muted)" }} />
        </div>
      </header>

      {/* ── 바디 (사이드바 + 컨텐츠) ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* 사이드바 */}
        <aside
          className="flex-shrink-0 flex flex-col z-20 transition-all duration-300"
          style={{
            width: sidebarOpen ? "200px" : "60px",
            borderRight: "1px solid var(--border)",
            background: "rgba(8,11,20,0.8)",
            backdropFilter: "blur(20px)",
          }}
        >
          {/* 탭 메뉴 */}
          <nav className="flex-1 p-2 pt-4 space-y-1" role="navigation" aria-label="주요 메뉴">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab)}
                  aria-label={tab.label}
                  aria-current={isActive ? "page" : undefined}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 focus:outline-none text-left"
                  style={{
                    background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                    border: isActive ? "1px solid rgba(99,102,241,0.25)" : "1px solid transparent",
                  }}
                >
                  <tab.Icon
                    size={17}
                    strokeWidth={isActive ? 2.5 : 1.8}
                    style={{ color: isActive ? "#818cf8" : "var(--text-muted)", flexShrink: 0 }}
                  />
                  {sidebarOpen && (
                    <span className="text-sm font-medium truncate"
                      style={{ color: isActive ? "#e0e7ff" : "var(--text-muted)" }}>
                      {tab.label}
                    </span>
                  )}
                  {isActive && sidebarOpen && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: "#818cf8" }} />
                  )}
                </button>
              );
            })}
          </nav>

          {/* 접기 버튼 */}
          <div className="p-2 pb-4">
            <button
              onClick={() => setSidebarOpen((p) => !p)}
              className="w-full flex items-center justify-center py-2 rounded-xl transition-colors focus:outline-none"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}
              aria-label={sidebarOpen ? "사이드바 접기" : "사이드바 펼치기"}
            >
              {sidebarOpen
                ? <ChevronLeft size={14} style={{ color: "var(--text-muted)" }} />
                : <ChevronRight size={14} style={{ color: "var(--text-muted)" }} />
              }
            </button>
          </div>
        </aside>

        {/* 메인 컨텐츠 */}
        <main id="main-content" className="flex-1 overflow-y-auto relative">
          <ActivePage />
        </main>

        {/* ── n8n 알림 패널 (Bell 클릭 시) ── */}
        {showNotifPanel && (
          <div
            className="absolute top-0 right-0 h-full flex flex-col z-40"
            style={{ width: "340px", background: "rgba(8,11,20,0.97)",
                     borderLeft: "1px solid var(--border)", backdropFilter: "blur(20px)" }}
          >
            <div className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2">
                <BotMessageSquare size={15} style={{ color: "#818cf8" }} />
                <span className="text-sm font-semibold" style={{ color: "#e0e7ff" }}>
                  n8n AI 리포트
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold"
                  style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>
                  {notifications.length}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setNotifications([])}
                  className="text-xs px-2 py-1 rounded focus:outline-none"
                  style={{ color: "var(--text-muted)", background: "rgba(255,255,255,0.05)" }}
                >
                  전체 삭제
                </button>
                <button onClick={() => setShowNotifPanel(false)} className="focus:outline-none" aria-label="패널 닫기">
                  <X size={14} style={{ color: "var(--text-muted)" }} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 gap-3">
                  <Zap size={28} style={{ color: "var(--text-muted)", opacity: 0.4 }} />
                  <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
                    n8n 워크플로우를 실행하면<br/>AI 리포트가 여기에 표시됩니다
                  </p>
                </div>
              ) : (
                notifications.map(n => {
                  const isExpanded = expandedId === n.id;
                  const gradeColor = n.grade === "A" ? "#10b981" : n.grade === "B" ? "#818cf8" : "#ef4444";
                  const gradeBg    = n.grade === "A" ? "rgba(16,185,129,0.2)" : n.grade === "B" ? "rgba(99,102,241,0.2)" : "rgba(239,68,68,0.2)";
                  return (
                    <div key={n.id}
                      className="rounded-xl p-3 space-y-2"
                      style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)" }}
                    >
                      {/* 헤더 행 */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold px-2 py-0.5 rounded"
                            style={{ background: gradeBg, color: gradeColor }}>
                            등급 {n.grade}
                          </span>
                          <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
                            {n.sentiment}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>{n.timestamp}</span>
                          <button onClick={() => speak(n.content || n.preview || `n8n 리포트. 시장 심리 ${n.score}점. ${n.sentiment}.`)}
                            className="text-xs px-2 py-0.5 rounded focus:outline-none"
                            style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8" }}
                            aria-label="전체 내용 음성으로 듣기" title="전체 내용 읽기">
                            ▶
                          </button>
                        </div>
                      </div>

                      {/* 공포탐욕 점수 바 */}
                      <div className="flex items-center gap-2">
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>공포탐욕</span>
                        <div className="flex-1 h-1.5 rounded-full overflow-hidden"
                          style={{ background: "rgba(255,255,255,0.08)" }}>
                          <div className="h-full rounded-full transition-all"
                            style={{ width: `${n.score}%`,
                                     background: n.score < 30 ? "#ef4444" : n.score < 50 ? "#f59e0b" : n.score < 70 ? "#10b981" : "#818cf8" }} />
                        </div>
                        <span className="text-xs font-bold" style={{ color: "var(--text-secondary)" }}>{n.score}</span>
                      </div>

                      {/* 본문 내용 - 펼치기/접기 */}
                      {n.content && (
                        <div>
                          <p className="text-xs leading-relaxed whitespace-pre-wrap"
                            style={{ color: "var(--text-secondary)", lineHeight: "1.6" }}>
                            {isExpanded ? n.content : n.content.slice(0, 160) + (n.content.length > 160 ? "…" : "")}
                          </p>
                          {n.content.length > 160 && (
                            <button
                              onClick={() => setExpandedId(isExpanded ? null : n.id)}
                              className="text-xs mt-1.5 focus:outline-none"
                              style={{ color: "#818cf8" }}>
                              {isExpanded ? "▲ 접기" : "▼ 전체 내용 보기"}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* 푸터: n8n 수동 실행 버튼 */}
            <div className="p-3" style={{ borderTop: "1px solid var(--border)" }}>
              <button
                onClick={async () => {
                  try {
                    await fetch("http://localhost:5678/webhook/vinvest-trigger");
                    speak("n8n AI 분석을 시작합니다. 잠시 후 리포트가 도착합니다.");
                  } catch {
                    speak("n8n 서버에 연결할 수 없습니다.");
                  }
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl font-semibold text-sm transition-all focus:outline-none"
                style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff" }}
                aria-label="n8n AI 분석 실행"
              >
                <Zap size={14} />
                n8n AI 분석 실행
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── n8n 토스트 알림 (새 리포트 도착 시 우하단 팝업) ── */}
      {n8nToast && (
        <div
          className="fixed bottom-6 right-6 z-50 rounded-2xl p-4 shadow-2xl flex items-start gap-3"
          style={{
            background: "rgba(15,18,35,0.98)", border: "1px solid rgba(99,102,241,0.4)",
            backdropFilter: "blur(20px)", minWidth: "280px", maxWidth: "340px",
            animation: "fadeIn 0.3s ease",
          }}
          role="alert" aria-live="polite"
        >
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
            <BotMessageSquare size={16} color="#fff" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-xs font-bold" style={{ color: "#818cf8" }}>n8n AI 리포트 도착</span>
              <button onClick={() => setN8nToast(null)} className="focus:outline-none flex-shrink-0">
                <X size={12} style={{ color: "var(--text-muted)" }} />
              </button>
            </div>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              시장 심리 <span className="font-bold" style={{ color: "#e0e7ff" }}>{n8nToast.score}점</span> · {n8nToast.sentiment} · 등급 <span className="font-bold" style={{ color: "#818cf8" }}>{n8nToast.grade}</span>
            </p>
            <button
              onClick={() => { setShowNotifPanel(true); setN8nToast(null); }}
              className="mt-1.5 text-xs underline focus:outline-none"
              style={{ color: "#818cf8" }}
            >
              자세히 보기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
