import { useEffect, useState, useRef } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";
import {
  TrendingUp, TrendingDown, Volume2, Activity,
  Zap, BarChart2, ChevronRight, Play, Clock,
  ArrowUpRight, ArrowDownRight, Radio,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip,
  CartesianGrid, LineChart, Line,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ASSETS = [
  { key: "btc",  label: "Bitcoin",    sub: "BTC",  unit: "$", color: "#f59e0b", bg: "rgba(245,158,11,0.08)",  type: "crypto" },
  { key: "eth",  label: "Ethereum",   sub: "ETH",  unit: "$", color: "#6366f1", bg: "rgba(99,102,241,0.08)",  type: "crypto" },
  { key: "sol",  label: "Solana",     sub: "SOL",  unit: "$", color: "#a78bfa", bg: "rgba(167,139,250,0.08)", type: "crypto" },
  { key: "aapl", label: "Apple Inc.", sub: "AAPL", unit: "$", color: "#10b981", bg: "rgba(16,185,129,0.08)",  type: "stock"  },
  { key: "nvda", label: "NVIDIA",     sub: "NVDA", unit: "$", color: "#8b5cf6", bg: "rgba(139,92,246,0.08)",  type: "stock"  },
  { key: "tsla", label: "Tesla",      sub: "TSLA", unit: "$", color: "#ef4444", bg: "rgba(239,68,68,0.08)",   type: "stock"  },
];

const SYMBOLS = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"];

const mock = (seed, len = 30) =>
  Array.from({ length: len }, (_, i) => ({
    t: `${i + 1}d`,
    v: 100 + Math.sin(i * 0.4 + seed) * 12 + (Math.random() - 0.5) * 6,
  }));

const EVENT_COLORS = {
  earnings: "#f59e0b",
  FOMC:     "#6366f1",
  CPI:      "#10b981",
  NFP:      "#f97316",
  macro:    "#06b6d4",
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-xl text-xs" style={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.08)", color: "#f1f5f9" }}>
      <p style={{ color: "var(--text-muted)" }}>{label}</p>
      <p className="font-bold mt-0.5" style={{ color: "#818cf8" }}>${payload[0].value.toFixed(2)}</p>
    </div>
  );
};

export default function Dashboard() {
  const { speak } = useTextToSpeech();
  const [prices,   setPrices]   = useState({});
  const [fearGreed, setFearGreed] = useState(null);
  const [report,   setReport]   = useState(null);
  const [sym,      setSym]      = useState("AAPL");
  const [chart,    setChart]    = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [loading,  setLoading]  = useState(true);
  const [pipeline, setPipeline] = useState({ status: "idle", progress: 0, step: "" });
  const [events,   setEvents]   = useState([]);
  const [newsFeed, setNewsFeed] = useState([]);
  const esRef = useRef(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetch(`${API_BASE}/market-data`).then(r => r.json());

        // 크립토: data.crypto.coins.btc.usd / usd_24h_change
        const coins = data?.crypto?.coins || {};
        const cryptoPrices = {};
        for (const [sym, coin] of Object.entries(coins)) {
          cryptoPrices[sym] = {
            price:  coin.usd,
            change: coin.usd_24h_change,
            high:   coin.high,
            low:    coin.low,
          };
        }

        // 주식: data.stocks.aapl.price / change
        const stocksRaw = data?.stocks || {};
        const stockPrices = {};
        for (const [sym, s] of Object.entries(stocksRaw)) {
          stockPrices[sym.toLowerCase()] = {
            price:  s.price,
            change: s.change,
            high:   s.high,
            low:    s.low,
          };
        }

        setPrices({ ...cryptoPrices, ...stockPrices });
        setFearGreed(data?.crypto?.fearGreed || null);
      } catch {}
      finally { setLoading(false); }
    };
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, []);

  // 경제 이벤트 캘린더
  useEffect(() => {
    fetch(`${API_BASE}/market-data/events`)
      .then(r => r.json())
      .then(d => setEvents(d.events || []))
      .catch(() => {});
  }, []);

  // 뉴스 피드 한국어 (5분마다 갱신)
  useEffect(() => {
    const loadNews = () => {
      fetch(`${API_BASE}/market-data/news/feed/ko?limit=20`)
        .then(r => r.json())
        .then(d => setNewsFeed(d.articles || []))
        .catch(() => {});
    };
    loadNews();
    const iv = setInterval(loadNews, 5 * 60 * 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    speak("V-Invest 대시보드입니다.");
  }, []); // eslint-disable-line

  useEffect(() => {
    const fetchChart = async () => {
      setChartLoading(true);
      try {
        // 크립토는 Yahoo Finance 심볼로 변환
        const symbolMap = { AAPL: "AAPL", NVDA: "NVDA", TSLA: "TSLA", MSFT: "MSFT", AMZN: "AMZN",
                            BTC: "BTC-USD", ETH: "ETH-USD", SOL: "SOL-USD" };
        const yfsym = symbolMap[sym] || sym;
        const res = await fetch(`${API_BASE}/market-data/history/${yfsym}?period=3mo`);
        const json = await res.json();
        if (json.data && json.data.length > 0) {
          setChart(json.data);
        } else {
          setChart(mock(SYMBOLS.indexOf(sym))); // 실패 시 fallback
        }
      } catch {
        setChart(mock(SYMBOLS.indexOf(sym)));
      } finally {
        setChartLoading(false);
      }
    };
    fetchChart();
  }, [sym]);

  useEffect(() => {
    // /analysis/stream: 파이프라인 진행 상황
    const es = new EventSource(`${API_BASE}/analysis/stream`);
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type === "progress") setPipeline({ status: "running", progress: d.progress ?? 0, step: d.step ?? "" });
        if (d.type === "complete") { setPipeline({ status: "done", progress: 100, step: "완료" }); setReport(d.report); }
      } catch {}
    };
    esRef.current = es;

    // /n8n/stream: n8n 워크플로우 리포트를 대시보드에도 반영
    const esN8n = new EventSource(`${API_BASE}/n8n/stream`);
    esN8n.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type !== "new_report") return;
        setReport({
          content:        d.content || d.preview || "",
          sentimentLabel: d.sentimentLabel,
          sentimentScore: d.sentimentScore,
          grade:          d.grade,
        });
      } catch {}
    };

    return () => { es.close(); esN8n.close(); };
  }, []);

  const runAnalysis = async () => {
    setPipeline({ status: "running", progress: 5, step: "파이프라인 시작..." });
    speak("AI 투자 분석을 시작합니다.");
    try { await fetch(`${API_BASE}/analysis/run`, { method: "POST" }); } catch {}
  };

  return (
    <div className="p-6 min-h-full" style={{ background: "var(--bg-primary)" }}>

      {/* ── 페이지 타이틀 ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>마켓 대시보드</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
            실시간 시장 현황 · AI 투자 분석
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
            style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <Radio size={10} color="#10b981" />
            <span style={{ color: "#10b981" }}>Live</span>
          </div>
          <button
            onClick={runAnalysis}
            disabled={pipeline.status === "running"}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 focus:outline-none"
            style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff" }}
          >
            <Play size={12} />
            AI 분석 실행
          </button>
        </div>
      </div>

      {/* ── 분석 파이프라인 진행바 ── */}
      {pipeline.status !== "idle" && (
        <div className="mb-5 p-4 rounded-2xl animate-fade-in"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold" style={{ color: pipeline.status === "done" ? "#10b981" : "#818cf8" }}>
              {pipeline.status === "done" ? "✓ 분석 완료" : `AI 분석 진행 중 — ${pipeline.step}`}
            </span>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>{pipeline.progress}%</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${pipeline.progress}%`,
                background: pipeline.status === "done"
                  ? "linear-gradient(90deg,#10b981,#06b6d4)"
                  : "linear-gradient(90deg,#6366f1,#8b5cf6)",
              }}
            />
          </div>
        </div>
      )}

      {/* ── 자산 카드 6개 ── */}
      <div className="grid grid-cols-6 gap-3 mb-5">
        {ASSETS.map((asset, idx) => {
          const price  = prices[asset.key] || {};
          const change = price.change ?? 0;
          const isUp   = change >= 0;

          return (
            <button
              key={asset.key}
              onClick={() => speak(`${asset.label}. ${price.price?.toLocaleString() || "데이터 없음"}달러. ${Math.abs(change).toFixed(2)}퍼센트 ${isUp ? "상승" : "하락"}.`)}
              aria-label={`${asset.label} 가격 정보`}
              className="card-hover text-left rounded-2xl p-4 focus:outline-none"
              style={{ background: asset.bg, border: `1px solid ${asset.color}22` }}
            >
              {loading ? (
                <>
                  <div className="skeleton h-2.5 w-10 mb-3 rounded" />
                  <div className="skeleton h-5 w-16 mb-1.5 rounded" />
                  <div className="skeleton h-2 w-10 rounded" />
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold" style={{ color: asset.color }}>{asset.sub}</span>
                    <span className="flex items-center gap-0.5 text-xs font-semibold"
                      style={{ color: isUp ? "#10b981" : "#ef4444" }}>
                      {isUp ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                      {Math.abs(change).toFixed(2)}%
                    </span>
                  </div>
                  <div className="text-lg font-black tracking-tight" style={{ color: "var(--text-primary)" }}>
                    {asset.unit}{price.price?.toLocaleString() ?? "—"}
                  </div>
                  <div className="text-xs mt-0.5 truncate" style={{ color: "var(--text-muted)" }}>
                    {asset.label}
                  </div>
                  {/* 스파크라인 */}
                  <div className="mt-2 h-6" aria-hidden="true">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={mock(idx, 12)}>
                        <Line type="monotone" dataKey="v" stroke={asset.color} strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}
            </button>
          );
        })}
      </div>

      {/* ── 메인 그리드 (차트 + 사이드 패널) ── */}
      <div className="grid grid-cols-3 gap-4 mb-4">

        {/* 메인 차트 - 2/3 너비 */}
        <div className="col-span-2 rounded-2xl p-5"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
                {sym} 가격 차트
              </h2>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                3개월 · 일봉 {chartLoading ? "· 불러오는 중…" : "· Yahoo Finance 실시간"}
              </p>
            </div>
            <div className="flex gap-1.5">
              {SYMBOLS.map((s) => (
                <button key={s}
                  onClick={() => setSym(s)}
                  aria-pressed={sym === s}
                  className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all focus:outline-none"
                  style={{
                    background: sym === s ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "rgba(255,255,255,0.05)",
                    color: sym === s ? "#fff" : "var(--text-muted)",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="h-52" aria-hidden="true">
            {chartLoading ? (
              <div className="h-full flex items-center justify-center">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Yahoo Finance 데이터 로딩 중…</p>
                </div>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="t" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false}
                    interval={Math.floor((chart.length || 1) / 6)} />
                  <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} domain={["auto","auto"]}
                    tickFormatter={v => `$${v >= 1000 ? (v/1000).toFixed(1)+"k" : v.toFixed(0)}`} width={52} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="v" stroke="#6366f1" strokeWidth={2}
                    fill="url(#areaGrad)" dot={false}
                    activeDot={{ r: 4, fill: "#6366f1", stroke: "#fff", strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* 우측 패널: 경제 이벤트 캘린더 */}
        <div className="rounded-2xl p-5 flex flex-col"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2 mb-4">
            <Clock size={14} style={{ color: "var(--text-muted)" }} />
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>경제 이벤트</h2>
            <span className="text-xs px-1.5 py-0.5 rounded-full ml-auto"
              style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8" }}>
              향후 45일
            </span>
          </div>

          {events.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>이벤트 로딩 중…</p>
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-60">
              {events.map((ev, i) => {
                const evDate  = new Date(ev.date + "T00:00:00");
                const today   = new Date(); today.setHours(0,0,0,0);
                const diffMs  = evDate - today;
                const diffDay = Math.round(diffMs / 86400000);
                const dateLabel = diffDay === 0 ? "오늘" : diffDay === 1 ? "내일" :
                                  diffDay < 0 ? `${Math.abs(diffDay)}일 전` : `${diffDay}일 후`;
                const color = ev.type === "earnings" ? EVENT_COLORS.earnings
                            : EVENT_COLORS[ev.symbol] || EVENT_COLORS.macro;
                return (
                  <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-xl"
                    style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                    <div className="w-1 min-h-8 rounded-full flex-shrink-0 mt-0.5"
                      style={{ background: color }} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                          {ev.label}
                        </p>
                        {ev.type === "earnings" && (
                          <span className="text-xs px-1.5 py-0.5 rounded font-bold"
                            style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b" }}>
                            실적
                          </span>
                        )}
                        {ev.type === "macro" && (
                          <span className="text-xs px-1.5 py-0.5 rounded font-bold"
                            style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8" }}>
                            {ev.symbol}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                          {ev.date}
                        </p>
                        <span className="text-xs font-semibold"
                          style={{ color: diffDay <= 3 ? "#ef4444" : diffDay <= 7 ? "#f59e0b" : "#475569" }}>
                          {dateLabel}
                        </span>
                      </div>
                      {ev.detail && ev.type === "earnings" && (
                        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{ev.detail}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-xs mt-3 pt-2" style={{ color: "var(--text-muted)", borderTop: "1px solid var(--border)" }}>
            출처: Finnhub · BLS · Fed 공식 스케줄
          </p>
        </div>
      </div>

      {/* ── 하단 그리드 (AI 리포트 + 시장 심리 + 빠른 액션) ── */}
      <div className="grid grid-cols-3 gap-4">

        {/* AI 리포트 */}
        <div className="col-span-2 rounded-2xl p-5"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap size={14} color="#818cf8" />
              <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>최신 AI 투자 리포트</h2>
            </div>
            {report && (
              <button onClick={() => speak(report.content || report.preview || "")}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors focus:outline-none"
                style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", color: "#818cf8" }}>
                <Volume2 size={11} /> 음성으로 듣기
              </button>
            )}
          </div>

          {report ? (
            <div className="space-y-3">
              {/* 태그 행 */}
              <div className="flex items-center gap-3 flex-wrap">
                {report.sentimentLabel && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                    style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8" }}>
                    {report.sentimentLabel}
                  </span>
                )}
                {report.grade && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                    style={{ background: "rgba(16,185,129,0.12)", color: "#10b981" }}>
                    등급 {report.grade}
                  </span>
                )}
                {report.sentimentScore !== undefined && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                    style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
                    심리점수 {report.sentimentScore}
                  </span>
                )}
              </div>
              {/* 전체 본문 — 스크롤 가능 */}
              <div className="rounded-xl p-4 max-h-64 overflow-y-auto"
                style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap"
                  style={{ color: "var(--text-secondary)", lineHeight: "1.75" }}>
                  {report.content || report.preview || "리포트 내용을 불러오는 중입니다."}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
                style={{ background: "rgba(99,102,241,0.1)" }}>
                <Activity size={20} style={{ color: "#818cf8" }} />
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                아직 분석 리포트가 없습니다
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                "AI 분석 실행" 버튼을 눌러 분석을 시작하세요
              </p>
            </div>
          )}
        </div>

        {/* 시장 심리 + 빠른 액션 */}
        <div className="space-y-3">
          {/* 공포 탐욕 게이지 */}
          <div className="rounded-2xl p-4"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center gap-2 mb-3">
              <BarChart2 size={13} style={{ color: "var(--text-muted)" }} />
              <h2 className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                공포&탐욕 지수
              </h2>
            </div>
            {fearGreed ? (() => {
              const val  = parseInt(fearGreed.value);
              const cl   = fearGreed.classification;
              const color = val < 25 ? "#ef4444" : val < 50 ? "#f97316" : val < 75 ? "#f59e0b" : "#10b981";
              const labelKo = cl === "Extreme Fear" ? "극도의 공포" : cl === "Fear" ? "공포" : cl === "Neutral" ? "중립" : cl === "Greed" ? "탐욕" : "극도의 탐욕";
              return (
                <>
                  <div className="flex items-end justify-between mb-2">
                    <span className="text-3xl font-black" style={{ color }}>{val}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full mb-1"
                      style={{ background: `${color}18`, color }}>
                      {labelKo}
                    </span>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                    <div className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${val}%`, background: "linear-gradient(90deg,#ef4444,#f97316,#f59e0b,#10b981)" }} />
                  </div>
                </>
              );
            })() : (
              <div className="skeleton h-12 rounded-xl" />
            )}
            <div className="flex justify-between mt-1">
              <span className="text-xs" style={{ color: "#ef4444" }}>공포</span>
              <span className="text-xs" style={{ color: "#10b981" }}>탐욕</span>
            </div>
          </div>

          {/* 빠른 액션 */}
          {[
            { label: "포트폴리오 최적화", sub: "PPO 강화학습 추론", color: "#6366f1", Icon: PieChartIcon },
            { label: "차트 AI 분석",     sub: "GPT-4o Vision",     color: "#10b981", Icon: EyeIcon },
          ].map((item) => (
            <button key={item.label}
              className="w-full rounded-2xl p-4 flex items-center gap-3 card-hover text-left focus:outline-none"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: `${item.color}18` }}>
                <item.Icon color={item.color} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{item.label}</p>
                <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{item.sub}</p>
              </div>
              <ChevronRight size={14} style={{ color: "var(--text-muted)" }} />
            </button>
          ))}
        </div>
      </div>

      {/* ── 실시간 뉴스 피드 ── */}
      <div className="mt-4 rounded-2xl p-5"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Radio size={14} style={{ color: "#ef4444" }} />
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>실시간 뉴스 피드</h2>
            <span className="text-xs px-1.5 py-0.5 rounded-full"
              style={{ background: "rgba(239,68,68,0.15)", color: "#ef4444" }}>LIVE</span>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Reuters · Bloomberg · CNBC · Finnhub
          </p>
        </div>

        {newsFeed.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="flex flex-col items-center gap-2">
              <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>뉴스 로딩 중…</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {newsFeed.slice(0, 18).map((article, i) => {
              const ts = article.timestamp
                ? (typeof article.timestamp === "number"
                    ? new Date(article.timestamp * 1000)
                    : new Date(article.timestamp))
                : null;
              const timeStr = ts
                ? ts.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
                : "";
              const dateStr = ts
                ? ts.toLocaleDateString("ko-KR", { month: "short", day: "numeric" })
                : "";
              const srcColor =
                article.source?.includes("Reuters") ? "#f97316" :
                article.source?.includes("Bloomberg") ? "#6366f1" :
                article.source?.includes("CNBC") ? "#10b981" :
                article.source?.includes("Yahoo") ? "#8b5cf6" : "#475569";
              return (
                <a key={i} href={article.url || "#"} target="_blank" rel="noopener noreferrer"
                  className="block p-3 rounded-xl transition-all group"
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}
                  onClick={() => speak(article.title_ko || article.title || "")}
                  aria-label={`뉴스: ${article.title_ko || article.title}`}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-xs font-bold px-1.5 py-0.5 rounded"
                      style={{ background: `${srcColor}18`, color: srcColor }}>
                      {article.source || "News"}
                    </span>
                    {(dateStr || timeStr) && (
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {dateStr} {timeStr}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-semibold leading-relaxed group-hover:text-indigo-400 transition-colors"
                    style={{ color: "var(--text-primary)", display: "-webkit-box",
                             WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {article.title_ko || article.title}
                  </p>
                  {(article.summary_ko || article.summary) && (
                    <p className="text-xs mt-1 leading-relaxed"
                      style={{ color: "var(--text-muted)", display: "-webkit-box",
                               WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                      {article.summary_ko || article.summary}
                    </p>
                  )}
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

const PieChartIcon = ({ color }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>
  </svg>
);
const EyeIcon = ({ color }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
  </svg>
);
