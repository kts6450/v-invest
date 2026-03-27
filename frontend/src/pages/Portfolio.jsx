/**
 * Portfolio - PPO 포트폴리오 최적화 페이지
 *
 * [화면 구성]
 *   1. PPO 추천 포트폴리오 (원형 차트 + 음성 설명)
 *   2. 자산별 비중 목록 (스크린 리더 최적화)
 *   3. 백테스트 결과 (PPO vs Buy&Hold)
 *   4. 새로고침 시 음성 알림 ("포트폴리오를 다시 계산합니다")
 *
 * [접근성]
 *   - 원형 차트는 시각 보조용, 데이터는 테이블로 중복 제공
 *   - 각 자산 비중을 aria-label에 포함
 *   - 추천 변경 시 aria-live로 자동 알림
 */
import { useState, useEffect } from "react";
import AudioPlayer from "../components/AudioPlayer";
import { useTextToSpeech } from "../hooks/useTextToSpeech";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ASSET_INFO = {
  BTC:  { label: "비트코인",  color: "#F7931A", emoji: "₿" },
  ETH:  { label: "이더리움",  color: "#627EEA", emoji: "Ξ" },
  SOL:  { label: "솔라나",    color: "#9945FF", emoji: "◎" },
  AAPL: { label: "애플",      color: "#00C49F", emoji: "🍎" },
  NVDA: { label: "엔비디아",  color: "#76FF03", emoji: "🎮" },
  TSLA: { label: "테슬라",    color: "#CC0000", emoji: "⚡" },
  CASH: { label: "현금",      color: "#95a5a6", emoji: "💵" },
};

export default function Portfolio() {
  const { speak } = useTextToSpeech();
  const [portfolio,  setPortfolio]  = useState(null);
  const [backtest,   setBacktest]   = useState(null);
  const [isLoading,  setIsLoading]  = useState(false);

  const loadPortfolio = async () => {
    setIsLoading(true);
    speak("포트폴리오를 최적화하고 있습니다. 잠시만 기다려 주세요.");
    try {
      const [portRes, btRes] = await Promise.all([
        fetch(`${API_BASE}/portfolio/recommend`).then((r) => r.json()),
        fetch(`${API_BASE}/portfolio/backtest?days=30`).then((r) => r.json()),
      ]);
      setPortfolio(portRes);
      setBacktest(btRes);
      speak(portRes.voice_summary);
    } catch {
      speak("포트폴리오 데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadPortfolio(); }, []); // eslint-disable-line

  const weights = portfolio?.weights || {};
  const sorted  = Object.entries(weights).sort(([, a], [, b]) => b - a);

  return (
    <main
      className="min-h-screen p-4 pb-20"
      style={{ background: "#0a0a0f", color: "#fff" }}
    >
      {/* 헤더 */}
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black" style={{ color: "#FFD700" }}>
            💼 포트폴리오
          </h1>
          <p className="text-xs text-gray-500">PPO 강화학습 최적화</p>
        </div>
        <button
          onClick={loadPortfolio}
          disabled={isLoading}
          aria-label="포트폴리오 다시 계산"
          className="
            px-4 py-2 rounded-xl font-bold text-sm
            focus:outline-none focus:ring-2 focus:ring-yellow-400
            disabled:opacity-50
          "
          style={{ background: "#1f2937" }}
        >
          {isLoading ? "계산 중..." : "🔄 갱신"}
        </button>
      </header>

      {/* PPO 음성 요약 */}
      {portfolio?.voice_summary && (
        <section aria-label="PPO 포트폴리오 음성 요약" className="mb-6">
          <AudioPlayer
            text={portfolio.voice_summary}
            title="PPO 포트폴리오 추천"
            autoPlay={false}
          />
        </section>
      )}

      {/* 자산 비중 목록 */}
      <section aria-label="자산별 투자 비중">
        <h2 className="text-sm text-gray-400 mb-3 font-semibold">추천 비중</h2>
        <ul role="list" className="space-y-2">
          {sorted.map(([asset, weight]) => {
            const info = ASSET_INFO[asset] || { label: asset, color: "#888", emoji: "•" };
            const pct  = (weight * 100).toFixed(1);
            return (
              <li
                key={asset}
                role="listitem"
                aria-label={`${info.label} ${pct}퍼센트`}
                className="flex items-center gap-3 rounded-xl p-3"
                style={{ background: "#111827" }}
              >
                <span aria-hidden="true" className="text-2xl w-8 text-center">
                  {info.emoji}
                </span>

                <div className="flex-1">
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-semibold">{info.label}</span>
                    <span className="text-sm font-bold" style={{ color: info.color }}>
                      {pct}%
                    </span>
                  </div>
                  {/* 진행 바 (시각 보조) */}
                  <div
                    className="h-2 rounded-full"
                    style={{ background: "#1f2937" }}
                    role="presentation"
                    aria-hidden="true"
                  >
                    <div
                      className="h-2 rounded-full transition-all duration-700"
                      style={{ width: `${pct}%`, background: info.color }}
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      {/* 백테스트 결과 */}
      {backtest && (
        <section aria-label="백테스트 성과 비교" className="mt-8">
          <h2 className="text-sm text-gray-400 mb-3 font-semibold">
            30일 백테스트
          </h2>

          {/* aria-live: 백테스트 결과 스크린 리더 자동 읽기 */}
          <div aria-live="polite" className="sr-only">
            {backtest.voice_summary}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <BacktestCard
              label="PPO 전략"
              data={backtest.ppo}
              highlight={true}
            />
            <BacktestCard
              label="단순 보유"
              data={backtest.buy_and_hold}
              highlight={false}
            />
          </div>

          {backtest.voice_summary && (
            <div className="mt-3">
              <AudioPlayer text={backtest.voice_summary} title="백테스트 결과 요약" />
            </div>
          )}
        </section>
      )}
    </main>
  );
}


// ── 백테스트 카드 ──
function BacktestCard({ label, data, highlight }) {
  return (
    <div
      className="rounded-2xl p-4"
      style={{
        background: highlight ? "#1a2744" : "#111827",
        border: highlight ? "1px solid #3b82f6" : "1px solid #374151",
      }}
      role="group"
      aria-label={`${label} 성과`}
    >
      <p className="text-xs text-gray-400 mb-2">{label}</p>
      <p
        className="text-2xl font-black"
        style={{ color: data?.return >= 0 ? "#00FF88" : "#FF4444" }}
        aria-label={`수익률 ${data?.return}퍼센트`}
      >
        {data?.return >= 0 ? "+" : ""}{data?.return}%
      </p>
      <p className="text-xs text-gray-500 mt-1">
        샤프 {data?.sharpe} · MDD {data?.max_dd}%
      </p>
    </div>
  );
}
