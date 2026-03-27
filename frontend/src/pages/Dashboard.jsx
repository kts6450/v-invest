/**
 * Dashboard - 시각 장애인 Voice-First 메인 대시보드
 *
 * [화면 진입 시 자동 동작]
 *   1. "V-Invest 대시보드입니다. 현재 시장 상황을 읽어드립니다." TTS 재생
 *   2. 주요 자산 가격 음성 요약 자동 재생
 *   3. n8n 새 리포트 도착 시 SSE로 수신 → 자동 TTS 알림
 *
 * [레이아웃]
 *   - 거대한 가격 카드 (글씨 크게, 고대비)
 *   - 차트 → AI 분석 버튼 → 음성으로 설명 청취
 *   - 하단 고정: 음성 입력 버튼
 */
import { useEffect, useState, useRef } from "react";
import { useTextToSpeech } from "../hooks/useTextToSpeech";
import HighContrastChart from "../components/HighContrastChart";
import AudioPlayer from "../components/AudioPlayer";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ASSETS = [
  { key: "btc",  label: "비트코인",  unit: "$", color: "#F7931A" },
  { key: "eth",  label: "이더리움",  unit: "$", color: "#627EEA" },
  { key: "aapl", label: "애플",      unit: "$", color: "#00C49F" },
  { key: "nvda", label: "엔비디아",  unit: "$", color: "#76FF03" },
];

export default function Dashboard() {
  const { speak } = useTextToSpeech();
  const [prices,     setPrices]     = useState({});
  const [latestReport, setLatest]   = useState(null);
  const [selectedSym,  setSelected] = useState("AAPL");
  const eventSourceRef = useRef(null);

  // ── 시장 데이터 폴링 (30초마다) ──
  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetch(`${API_BASE}/market-data`).then((r) => r.json()); // 기존 엔드포인트 재활용
        setPrices(data.crypto || {});
      } catch {}
    };
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  // ── 진입 시 음성 환영 메시지 ──
  useEffect(() => {
    speak("V-Invest 대시보드에 오신 것을 환영합니다. 시장 데이터를 불러오고 있습니다.");
  }, []); // eslint-disable-line

  // ── n8n SSE: 새 리포트 실시간 수신 ──
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/n8n/stream`);
    es.onmessage = (e) => {
      try {
        const report = JSON.parse(e.data);
        if (report.type === "new_report") {
          setLatest(report);
          // 시각 장애인: 새 리포트 도착 즉시 TTS 알림
          speak(
            `새 AI 투자 리포트가 도착했습니다. 시장 심리 ${report.sentimentLabel}, ` +
            `점수 ${report.sentimentScore}점입니다. 리포트 탭에서 자세한 내용을 들으실 수 있습니다.`
          );
        }
      } catch {}
    };
    eventSourceRef.current = es;
    return () => es.close();
  }, [speak]);

  // ── 자산 카드 클릭 → 가격 TTS 읽기 ──
  const handleCardFocus = (asset, price) => {
    const change = price?.change;
    const dir    = change >= 0 ? "상승" : "하락";
    speak(
      `${asset.label}. 현재가 ${price?.price?.toLocaleString() || "데이터 없음"}달러. ` +
      `${Math.abs(change || 0).toFixed(2)}퍼센트 ${dir}.`
    );
  };

  return (
    <main
      className="min-h-screen p-4 pb-28"
      style={{ background: "#0a0a0f", color: "#fff" }}
    >
      {/* 헤더 */}
      <header className="mb-6">
        <h1 className="text-3xl font-black tracking-tight" style={{ color: "#FFD700" }}>
          V-Invest
        </h1>
        <p className="text-gray-400 text-sm mt-1">AI 투자 어시스턴트</p>
      </header>

      {/* 자산 가격 카드 */}
      <section aria-label="실시간 자산 가격">
        <h2 className="sr-only">실시간 가격</h2>
        <div className="grid grid-cols-2 gap-3 mb-6">
          {ASSETS.map((asset) => {
            const price  = prices[asset.key] || {};
            const change = price.change ?? 0;
            return (
              <button
                key={asset.key}
                onClick={() => handleCardFocus(asset, price)}
                aria-label={`${asset.label} ${price.price?.toFixed(2) || "-"} 달러. ${Math.abs(change).toFixed(2)}퍼센트 ${change >= 0 ? "상승" : "하락"}. 탭하면 음성으로 읽어드립니다.`}
                className="
                  rounded-2xl p-4 text-left
                  transition-transform active:scale-95
                  focus:outline-none focus:ring-4 focus:ring-yellow-400
                "
                style={{ background: "#111827", border: `1px solid ${asset.color}33` }}
              >
                <div className="text-xs text-gray-400 mb-1">{asset.label}</div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: asset.color }}
                  aria-hidden="true"
                >
                  {asset.unit}{price.price?.toLocaleString() || "—"}
                </div>
                <div
                  className="text-sm mt-1 font-semibold"
                  style={{ color: change >= 0 ? "#00FF88" : "#FF4444" }}
                  aria-hidden="true"
                >
                  {change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 차트 섹션 */}
      <section aria-label="주식 차트 분석" className="mb-6">
        <div className="flex gap-2 mb-3">
          {["AAPL", "NVDA", "TSLA"].map((sym) => (
            <button
              key={sym}
              onClick={() => { setSelected(sym); speak(`${sym} 차트로 전환합니다.`); }}
              aria-pressed={selectedSym === sym}
              className="px-4 py-2 rounded-xl text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
              style={{
                background: selectedSym === sym ? "#FFD700" : "#1f2937",
                color:      selectedSym === sym ? "#000"    : "#fff",
              }}
            >
              {sym}
            </button>
          ))}
        </div>
        <HighContrastChart symbol={selectedSym} />
      </section>

      {/* 최신 n8n 리포트 알림 */}
      {latestReport && (
        <section aria-label="최신 AI 리포트" className="mb-6">
          <AudioPlayer
            text={latestReport.preview}
            title="최신 AI 투자 리포트"
            autoPlay={false}
          />
        </section>
      )}
    </main>
  );
}
