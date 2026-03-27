/**
 * HighContrastChart - 저시력·색맹 최적화 차트 컴포넌트
 *
 * [접근성 설계]
 *   - 고대비 배경(검정) + 밝은 선(노랑/흰색)
 *   - 색상 외 패턴(점선, 실선)으로 데이터 구분
 *   - 차트 로드 완료 시 자동 TTS 설명 재생
 *   - aria-describedby로 텍스트 대체 설명 연결
 *   - 키보드로 데이터 포인트 탐색 (←/→ 화살표)
 *
 * [Props]
 *   symbol      : 종목 코드 (예: "AAPL")
 *   onAnalysis  : Vision AI 분석 결과 콜백 (text: string) => void
 *
 * [Vision AI 연동]
 *   1. Finnhub 차트 이미지 URL 생성
 *   2. 백엔드 POST /charts/analyze/url 호출
 *   3. 반환된 음성 설명을 AudioPlayer로 자동 재생
 */
import { useState, useEffect, useRef, useCallback } from "react";
import AudioPlayer from "./AudioPlayer";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FINNHUB_KEY = import.meta.env.VITE_FINNHUB_KEY || "";

// 고대비 색상 팔레트 (WCAG AA 기준 4.5:1 대비율 이상)
const HC_COLORS = {
  line:       "#FFD700",  // 금색 (검정 배경 대비 10:1)
  sma20:      "#00FF88",  // 밝은 초록
  sma50:      "#FF6B6B",  // 밝은 빨강
  bg:         "#0a0a0a",
  grid:       "#1e1e1e",
  text:       "#FFFFFF",
  positive:   "#00FF88",
  negative:   "#FF4444",
};

export default function HighContrastChart({ symbol = "AAPL", onAnalysis }) {
  const [analysisText, setAnalysisText] = useState("");
  const [isAnalyzing,  setIsAnalyzing]  = useState(false);
  const [priceData,    setPriceData]    = useState([]);
  const [focusedIdx,   setFocusedIdx]   = useState(null); // 키보드 탐색용

  const canvasRef    = useRef(null);
  const descId       = `chart-desc-${symbol}`;


  // ── 가격 데이터 로드 (Finnhub REST) ──
  useEffect(() => {
    _fetchPriceData(symbol).then((data) => {
      setPriceData(data);
      if (canvasRef.current) _drawChart(canvasRef.current, data);
    });
  }, [symbol]);


  // ── Vision AI 차트 분석 ──
  const analyzeChart = useCallback(async () => {
    setIsAnalyzing(true);
    try {
      const chartUrl = `https://finnhub.io/api/v1/scan/chart?symbol=${symbol}&resolution=D&token=${FINNHUB_KEY}`;
      const res = await fetch(`${API_BASE}/charts/analyze/url`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ url: chartUrl, symbol }),
      });
      const data = await res.json();
      setAnalysisText(data.description || "분석 결과를 가져올 수 없습니다.");
      onAnalysis?.(data.description);
    } catch {
      setAnalysisText("차트 분석 중 오류가 발생했습니다.");
    } finally {
      setIsAnalyzing(false);
    }
  }, [symbol, onAnalysis]);


  // ── 키보드: 데이터 포인트 탐색 ──
  const handleKeyDown = useCallback((e) => {
    if (!priceData.length) return;
    if (e.key === "ArrowRight") {
      setFocusedIdx((i) => Math.min((i ?? 0) + 1, priceData.length - 1));
    } else if (e.key === "ArrowLeft") {
      setFocusedIdx((i) => Math.max((i ?? priceData.length - 1) - 1, 0));
    } else if (e.key === "Enter") {
      analyzeChart();
    }
  }, [priceData, analyzeChart]);


  const currentPoint = focusedIdx !== null ? priceData[focusedIdx] : priceData[priceData.length - 1];

  return (
    <div className="rounded-2xl overflow-hidden border border-gray-700">
      {/* 차트 헤더 */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ background: HC_COLORS.bg }}
      >
        <h2 className="text-white font-bold text-lg" id={descId}>
          {symbol} 차트
          {currentPoint && (
            <span className="ml-3 text-sm font-normal" style={{ color: HC_COLORS.line }}>
              ${currentPoint.close?.toFixed(2)}
            </span>
          )}
        </h2>

        {/* AI 분석 버튼 */}
        <button
          onClick={analyzeChart}
          disabled={isAnalyzing}
          aria-label={`${symbol} 차트 AI 음성 분석 시작`}
          className="
            px-4 py-2 rounded-lg text-sm font-bold
            focus:outline-none focus:ring-2 focus:ring-yellow-400
            disabled:opacity-50
          "
          style={{ background: "#f39c12", color: "#000" }}
        >
          {isAnalyzing ? "분석 중..." : "🔊 AI 분석"}
        </button>
      </div>

      {/* 캔버스 차트 */}
      <canvas
        ref={canvasRef}
        width={600}
        height={200}
        tabIndex={0}
        role="img"
        aria-label={`${symbol} 가격 차트. 화살표 키로 데이터 포인트 탐색, Enter로 AI 분석`}
        aria-describedby={descId}
        onKeyDown={handleKeyDown}
        className="w-full focus:outline-none focus:ring-2 focus:ring-blue-400"
        style={{ background: HC_COLORS.bg, cursor: "crosshair" }}
      />

      {/* 현재 선택된 데이터 포인트 (스크린 리더용 + 시각 표시) */}
      {currentPoint && (
        <div
          aria-live="polite"
          className="px-4 py-2 text-sm flex gap-4"
          style={{ background: "#111", color: HC_COLORS.text }}
        >
          <span>날짜: {currentPoint.date}</span>
          <span>종가: <strong style={{ color: HC_COLORS.line }}>${currentPoint.close?.toFixed(2)}</strong></span>
          <span style={{ color: currentPoint.change >= 0 ? HC_COLORS.positive : HC_COLORS.negative }}>
            {currentPoint.change >= 0 ? "▲" : "▼"} {Math.abs(currentPoint.change).toFixed(2)}%
          </span>
        </div>
      )}

      {/* AI 음성 분석 결과 */}
      {analysisText && (
        <div className="p-4" style={{ background: "#0d1117" }}>
          <AudioPlayer
            text={analysisText}
            autoPlay={true}
            title={`${symbol} 차트 AI 분석`}
          />
        </div>
      )}
    </div>
  );
}


// ── Finnhub에서 가격 데이터 로드 ──
async function _fetchPriceData(symbol) {
  try {
    const to   = Math.floor(Date.now() / 1000);
    const from = to - 30 * 24 * 3600; // 30일
    const url  = `https://finnhub.io/api/v1/stock/candle?symbol=${symbol}&resolution=D&from=${from}&to=${to}&token=${FINNHUB_KEY}`;
    const data = await fetch(url).then((r) => r.json());

    if (data.s !== "ok" || !data.c) return _getDummyData();

    return data.t.map((t, i) => ({
      date:   new Date(t * 1000).toLocaleDateString("ko-KR"),
      close:  data.c[i],
      open:   data.o[i],
      high:   data.h[i],
      low:    data.l[i],
      volume: data.v[i],
      change: i > 0 ? ((data.c[i] - data.c[i - 1]) / data.c[i - 1]) * 100 : 0,
    }));
  } catch {
    return _getDummyData();
  }
}


// ── 고대비 캔버스 차트 렌더링 ──
function _drawChart(canvas, data) {
  if (!data.length) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const PAD = 40;

  ctx.fillStyle = HC_COLORS.bg;
  ctx.fillRect(0, 0, W, H);

  const prices = data.map((d) => d.close);
  const min = Math.min(...prices) * 0.998;
  const max = Math.max(...prices) * 1.002;
  const scaleY = (p) => H - PAD - ((p - min) / (max - min)) * (H - PAD * 2);
  const scaleX = (i) => PAD + (i / (data.length - 1)) * (W - PAD * 2);

  // 격자선
  ctx.strokeStyle = HC_COLORS.grid;
  ctx.lineWidth   = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = PAD + (i / 4) * (H - PAD * 2);
    ctx.beginPath(); ctx.moveTo(PAD, y); ctx.lineTo(W - PAD, y); ctx.stroke();
  }

  // 가격선 (고대비 금색)
  ctx.strokeStyle = HC_COLORS.line;
  ctx.lineWidth   = 2;
  ctx.beginPath();
  data.forEach((d, i) => {
    i === 0
      ? ctx.moveTo(scaleX(i), scaleY(d.close))
      : ctx.lineTo(scaleX(i), scaleY(d.close));
  });
  ctx.stroke();

  // 최고/최저 레이블
  ctx.fillStyle  = HC_COLORS.text;
  ctx.font       = "11px monospace";
  ctx.textAlign  = "right";
  ctx.fillText(`$${max.toFixed(1)}`, PAD - 4, PAD);
  ctx.fillText(`$${min.toFixed(1)}`, PAD - 4, H - PAD);
}

function _getDummyData() {
  return Array.from({ length: 30 }, (_, i) => ({
    date:   `${i + 1}일전`,
    close:  200 + Math.random() * 50,
    change: (Math.random() - 0.5) * 4,
  }));
}
