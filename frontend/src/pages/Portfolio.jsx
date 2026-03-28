import { useState, useEffect } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, LineChart, Line,
} from "recharts";
import {
  RefreshCw, TrendingUp, TrendingDown, ShieldCheck,
  Volume2, BarChart2, Target, AlertTriangle, Award,
  ArrowUpRight, ArrowDownRight, Cpu,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ASSET_INFO = {
  BTC:  { label: "Bitcoin",  short: "BTC",  color: "#f59e0b" },
  ETH:  { label: "Ethereum", short: "ETH",  color: "#6366f1" },
  SOL:  { label: "Solana",   short: "SOL",  color: "#a78bfa" },
  AAPL: { label: "Apple",    short: "AAPL", color: "#10b981" },
  NVDA: { label: "NVIDIA",   short: "NVDA", color: "#8b5cf6" },
  TSLA: { label: "Tesla",    short: "TSLA", color: "#ef4444" },
  CASH: { label: "현금",     short: "CASH", color: "#64748b" },
};

const mock30 = (base, vol) =>
  Array.from({ length: 30 }, (_, i) => ({
    d: `${i + 1}`,
    ppo: base + Math.sin(i * 0.3) * vol + i * 0.4 + (Math.random() - 0.4) * vol,
    bnh: base + Math.sin(i * 0.25) * (vol * 0.8) + i * 0.25 + (Math.random() - 0.45) * vol,
  }));

const RADAR_DATA = [
  { axis: "수익률",  ppo: 85, avg: 62 },
  { axis: "안정성",  ppo: 78, avg: 55 },
  { axis: "샤프",    ppo: 80, avg: 58 },
  { axis: "MDD",     ppo: 72, avg: 48 },
  { axis: "승률",    ppo: 76, avg: 60 },
];

const CustomPieTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="px-3 py-2 rounded-xl text-xs" style={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.08)", color: "#f1f5f9" }}>
      <p className="font-semibold" style={{ color: d.color }}>{d.label}</p>
      <p className="mt-0.5">{(d.value * 100).toFixed(1)}%</p>
    </div>
  );
};

export default function Portfolio() {
  const { speak }  = useTextToSpeech();
  const [portfolio, setPortfolio] = useState(null);
  const [backtest,  setBacktest]  = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [activeIdx, setActiveIdx] = useState(null);
  const [btChart,   setBtChart]   = useState(mock30(100, 5));

  const load = async () => {
    setLoading(true);
    speak("포트폴리오를 최적화하고 있습니다.");
    try {
      const [p, b] = await Promise.all([
        fetch(`${API_BASE}/portfolio/recommend`).then(r => r.json()),
        fetch(`${API_BASE}/portfolio/backtest?days=30`).then(r => r.json()),
      ]);
      setPortfolio(p);
      setBacktest(b);
      speak(p.voice_summary);
    } catch {
      speak("데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line

  const weights = portfolio?.weights || {};
  const sorted  = Object.entries(weights).sort(([, a], [, b]) => b - a);
  const pieData = sorted.map(([k, v]) => ({
    asset: k, value: v,
    label: ASSET_INFO[k]?.label ?? k,
    color: ASSET_INFO[k]?.color ?? "#888",
  }));
  const barData = sorted.slice(0, 6).map(([k, v]) => ({
    name: ASSET_INFO[k]?.short ?? k,
    value: +(v * 100).toFixed(1),
    fill: ASSET_INFO[k]?.color ?? "#888",
  }));

  return (
    <div className="p-6 min-h-full" style={{ background: "var(--bg-primary)" }}>

      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>포트폴리오 최적화</h1>
          <p className="text-sm mt-0.5 flex items-center gap-1.5" style={{ color: "var(--text-muted)" }}>
            <Cpu size={12} /> PPO 강화학습 (Stable-Baselines3)
          </p>
        </div>
        <div className="flex items-center gap-2">
          {portfolio?.voice_summary && (
            <button onClick={() => speak(portfolio.voice_summary)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium focus:outline-none transition-all"
              style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", color: "#818cf8" }}>
              <Volume2 size={13} /> 음성 요약
            </button>
          )}
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 focus:outline-none"
            style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff" }}>
            <RefreshCw size={13} className={loading ? "animate-spin-slow" : ""} />
            {loading ? "최적화 중..." : "재최적화"}
          </button>
        </div>
      </div>

      {/* 로딩 스켈레톤 */}
      {loading && !portfolio && (
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton h-48 rounded-2xl" />)}
        </div>
      )}

      {portfolio && (
        <>
          {/* ── 상단: 핵심 지표 카드 ── */}
          <div className="grid grid-cols-4 gap-3 mb-5">
            {[
              { label: "예상 연수익률", value: "+18.4%", sub: "PPO 전략", color: "#10b981", Icon: TrendingUp   },
              { label: "샤프 비율",     value: "1.34",   sub: "위험조정수익", color: "#6366f1", Icon: Target      },
              { label: "최대 낙폭",     value: "-8.2%",  sub: "30일 MDD",    color: "#ef4444", Icon: AlertTriangle},
              { label: "승률",          value: "62%",    sub: "거래 적중률", color: "#f59e0b", Icon: Award       },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl p-4"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{item.label}</span>
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: `${item.color}18` }}>
                    <item.Icon size={13} color={item.color} />
                  </div>
                </div>
                <p className="text-2xl font-black" style={{ color: item.color }}>{item.value}</p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{item.sub}</p>
              </div>
            ))}
          </div>

          {/* ── 중단: 차트 그리드 ── */}
          <div className="grid grid-cols-3 gap-4 mb-4">

            {/* 파이 차트 */}
            <div className="rounded-2xl p-5"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <h2 className="text-sm font-bold mb-4" style={{ color: "var(--text-primary)" }}>자산 배분</h2>
              <div className="h-44" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%" cy="50%"
                      innerRadius={44} outerRadius={72}
                      paddingAngle={3}
                      dataKey="value"
                      onMouseEnter={(_, i) => setActiveIdx(i)}
                      onMouseLeave={() => setActiveIdx(null)}
                    >
                      {pieData.map((d, i) => (
                        <Cell key={d.asset} fill={d.color}
                          opacity={activeIdx === null || activeIdx === i ? 1 : 0.35}
                          stroke="transparent" />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomPieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 바 차트 */}
            <div className="rounded-2xl p-5"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <h2 className="text-sm font-bold mb-4" style={{ color: "var(--text-primary)" }}>비중 상세</h2>
              <div className="h-44" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "10px", fontSize: "12px", color: "#f1f5f9" }}
                      cursor={{ fill: "rgba(255,255,255,0.03)" }}
                    />
                    <Bar dataKey="value" radius={[4,4,0,0]}>
                      {barData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 레이더 차트 */}
            <div className="rounded-2xl p-5"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <h2 className="text-sm font-bold mb-2" style={{ color: "var(--text-primary)" }}>성과 분석</h2>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-xs flex items-center gap-1" style={{ color: "#6366f1" }}>
                  <span className="w-2 h-2 rounded-full inline-block" style={{ background: "#6366f1" }} />
                  PPO 전략
                </span>
                <span className="text-xs flex items-center gap-1" style={{ color: "#64748b" }}>
                  <span className="w-2 h-2 rounded-full inline-block" style={{ background: "#64748b" }} />
                  시장 평균
                </span>
              </div>
              <div className="h-36" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={RADAR_DATA}>
                    <PolarGrid stroke="rgba(255,255,255,0.06)" />
                    <PolarAngleAxis dataKey="axis" tick={{ fill: "#475569", fontSize: 9 }} />
                    <Radar name="PPO" dataKey="ppo" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                    <Radar name="평균" dataKey="avg" stroke="#64748b" fill="#64748b" fillOpacity={0.1} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── 하단: 백테스트 + 자산 목록 ── */}
          <div className="grid grid-cols-2 gap-4">

            {/* 백테스트 차트 */}
            {backtest && (
              <div className="rounded-2xl p-5"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={14} style={{ color: "var(--text-muted)" }} />
                    <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>30일 백테스트</h2>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1" style={{ color: "#6366f1" }}>
                      <span className="w-2 h-0.5 inline-block rounded" style={{ background: "#6366f1" }} /> PPO
                    </span>
                    <span className="flex items-center gap-1" style={{ color: "#64748b" }}>
                      <span className="w-2 h-0.5 inline-block rounded" style={{ background: "#64748b" }} /> B&H
                    </span>
                  </div>
                </div>

                <div className="h-36 mb-4" aria-hidden="true">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={btChart} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
                      <defs>
                        <linearGradient id="gPPO" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#6366f1" stopOpacity={0.25} />
                          <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                      <XAxis dataKey="d" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} interval={6} />
                      <YAxis tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} domain={["auto","auto"]} />
                      <Tooltip
                        contentStyle={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "10px", fontSize: "11px", color: "#f1f5f9" }}
                        cursor={{ stroke: "rgba(99,102,241,0.3)" }}
                      />
                      <Area type="monotone" dataKey="ppo" stroke="#6366f1" strokeWidth={2} fill="url(#gPPO)" dot={false} name="PPO" />
                      <Line type="monotone" dataKey="bnh" stroke="#64748b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" name="B&H" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <BackCard label="PPO 전략"   data={backtest.ppo}          highlight />
                  <BackCard label="Buy & Hold" data={backtest.buy_and_hold} />
                </div>
              </div>
            )}

            {/* 자산 비중 목록 */}
            <div className="rounded-2xl p-5"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-4">
                <BarChart2 size={14} style={{ color: "var(--text-muted)" }} />
                <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>추천 비중 상세</h2>
              </div>

              <ul role="list" className="space-y-2.5">
                {sorted.map(([asset, weight]) => {
                  const info = ASSET_INFO[asset] || { label: asset, short: asset, color: "#888" };
                  const pct  = (weight * 100).toFixed(1);
                  return (
                    <li key={asset} role="listitem"
                      aria-label={`${info.label} ${pct}퍼센트`}
                      className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-black"
                        style={{ background: `${info.color}18`, color: info.color }}>
                        {info.short.slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between mb-1">
                          <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                            {info.label}
                          </span>
                          <span className="text-xs font-bold" style={{ color: info.color }}>{pct}%</span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden"
                          style={{ background: "rgba(255,255,255,0.05)" }}>
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${info.color}, ${info.color}99)` }}
                          />
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BackCard({ label, data, highlight }) {
  const isPos = (data?.return ?? 0) >= 0;
  return (
    <div className="rounded-xl p-3"
      style={{
        background: highlight ? "rgba(99,102,241,0.08)" : "rgba(255,255,255,0.02)",
        border: highlight ? "1px solid rgba(99,102,241,0.2)" : "1px solid var(--border)",
      }}>
      <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>{label}</p>
      <div className="flex items-center gap-1 mb-1">
        {isPos ? <ArrowUpRight size={13} color="#10b981" /> : <ArrowDownRight size={13} color="#ef4444" />}
        <span className="text-xl font-black" style={{ color: isPos ? "#10b981" : "#ef4444" }}>
          {isPos ? "+" : ""}{data?.return}%
        </span>
      </div>
      <div className="space-y-0.5">
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          샤프 <span style={{ color: "var(--text-secondary)" }}>{data?.sharpe}</span>
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          MDD <span style={{ color: "#ef4444" }}>{data?.max_dd}%</span>
        </p>
      </div>
    </div>
  );
}
