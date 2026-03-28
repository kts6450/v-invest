"""
RAG 지식베이스 초기 데이터 적재 스크립트
NewsAPI, FRED, Yahoo Finance 뉴스, 금융 지식을 ChromaDB에 저장합니다.

[실행]
  cd backend
  .\\venv\\Scripts\\python seed_rag.py
"""
import os, sys, requests, json
from datetime import datetime, timedelta
from pathlib import Path

# .env 파일 직접 파싱 (python-dotenv 우회)
env_path = Path(__file__).parent / ".env"

def _parse_env(path: Path) -> dict:
    """BOM, 주석, 인라인 주석 모두 처리하는 .env 파서"""
    result = {}
    if not path.exists():
        return result
    text = path.read_bytes().decode("utf-8-sig")  # UTF-8 BOM 제거
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split("#")[0].strip()  # 인라인 주석 제거
        result[key.strip()] = val
    return result

_env_vars = _parse_env(env_path)
for k, v in _env_vars.items():
    os.environ.setdefault(k, v)

NEWS_KEY   = _env_vars.get("NEWS_API_KEY", "")
FRED_KEY   = _env_vars.get("FRED_API_KEY", "")
OPENAI_KEY = _env_vars.get("OPENAI_API_KEY", "")

if not OPENAI_KEY:
    print(f"오류: OPENAI_API_KEY 없음. {env_path}")
    sys.exit(1)

print(f"API 키 로드 완료 (OPENAI: ...{OPENAI_KEY[-8:]})")

# ── ChromaDB 직접 연결 ──
sys.path.insert(0, str(Path(__file__).parent))
from app.services.rag_service import KnowledgeBase

kb = KnowledgeBase()
total_added = 0


def add(content: str, doc_type: str, source: str, date: str = ""):
    global total_added
    n = kb.add_report(content, doc_type=doc_type, source=source, date=date or today())
    total_added += n
    return n


def today():
    return datetime.now().strftime("%Y-%m-%d")


# ════════════════════════════════════════════════════════
# 1. NewsAPI — 금융/투자 최신 뉴스
# ════════════════════════════════════════════════════════
def fetch_newsapi():
    print("\n[1] NewsAPI 금융 뉴스 수집 중...")
    if not NEWS_KEY:
        print("  NEWS_API_KEY 없음 — 스킵")
        return

    queries = [
        "Bitcoin cryptocurrency investment 2025",
        "NVIDIA stock AI semiconductor earnings",
        "Federal Reserve interest rate inflation 2025",
        "S&P 500 stock market outlook 2025",
        "Tesla Apple Microsoft earnings revenue",
    ]
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    for q in queries:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": q, "from": from_date, "sortBy": "relevancy",
                "language": "en", "pageSize": 10, "apiKey": NEWS_KEY,
            }
            r = requests.get(url, params=params, timeout=10)
            articles = r.json().get("articles", [])

            for art in articles:
                title   = art.get("title", "")
                desc    = art.get("description") or ""
                content = art.get("content") or ""
                text    = f"제목: {title}\n\n{desc}\n\n{content}".strip()
                if len(text) < 100:
                    continue
                n = add(text, "news", art.get("source", {}).get("name", "NewsAPI"), art.get("publishedAt", "")[:10])
                print(f"  + {title[:60]}... ({n}청크)")

        except Exception as e:
            print(f"  오류: {e}")


# ════════════════════════════════════════════════════════
# 2. Yahoo Finance 뉴스 (API 키 불필요)
# ════════════════════════════════════════════════════════
def fetch_yahoo_news():
    print("\n[2] Yahoo Finance 종목 뉴스 수집 중...")
    symbols = ["AAPL", "NVDA", "TSLA", "MSFT", "BTC-USD", "ETH-USD"]

    for sym in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
            r   = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]

            price     = meta.get("regularMarketPrice", 0)
            prev      = meta.get("chartPreviousClose", price)
            change    = round((price - prev) / prev * 100, 2) if prev else 0
            direction = "상승" if change >= 0 else "하락"
            sym_kr    = {"AAPL":"애플","NVDA":"엔비디아","TSLA":"테슬라","MSFT":"마이크로소프트","BTC-USD":"비트코인","ETH-USD":"이더리움"}.get(sym, sym)

            text = (
                f"[실시간 시세 {today()}]\n"
                f"{sym_kr}({sym}) 현재가: ${price:,.2f}\n"
                f"전일 대비: {change:+.2f}% {direction}\n"
                f"52주 최고: ${meta.get('fiftyTwoWeekHigh', 'N/A')}\n"
                f"52주 최저: ${meta.get('fiftyTwoWeekLow', 'N/A')}\n"
                f"시장: {meta.get('fullExchangeName', 'N/A')}"
            )
            n = add(text, "price_data", f"Yahoo Finance/{sym}", today())
            print(f"  + {sym_kr} 시세 정보 ({n}청크)")
        except Exception as e:
            print(f"  {sym} 오류: {e}")


# ════════════════════════════════════════════════════════
# 3. FRED — 매크로 경제 지표
# ════════════════════════════════════════════════════════
def fetch_fred():
    print("\n[3] FRED 매크로 경제 지표 수집 중...")
    if not FRED_KEY:
        print("  FRED_API_KEY 없음 — 내장 데이터 사용")
        _add_builtin_macro()
        return

    series = {
        "FEDFUNDS":  ("연방기금금리", "Federal Funds Rate"),
        "CPIAUCSL":  ("소비자물가지수 CPI", "Consumer Price Index"),
        "UNRATE":    ("실업률", "Unemployment Rate"),
        "GDP":       ("GDP 성장률", "GDP"),
        "T10Y2Y":    ("장단기 금리 스프레드", "10Y-2Y Treasury Spread"),
        "VIXCLS":    ("VIX 변동성 지수", "CBOE Volatility Index"),
        "SP500":     ("S&P 500 지수", "S&P 500"),
        "DCOILWTICO":("WTI 원유 가격", "Crude Oil WTI"),
        "GOLDAMGBD228NLBM": ("금 가격", "Gold Price"),
    }

    for series_id, (name_kr, name_en) in series.items():
        try:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id, "api_key": FRED_KEY,
                "file_type": "json", "limit": 12,
                "sort_order": "desc",
            }
            r    = requests.get(url, params=params, timeout=10)
            obs  = r.json().get("observations", [])
            if not obs:
                continue

            recent = [(o["date"], o["value"]) for o in obs if o["value"] != "."][:6]
            values_str = "\n".join(f"  {d}: {v}" for d, v in recent)
            latest_val = recent[0][1] if recent else "N/A"

            text = (
                f"[FRED 경제지표 — {name_kr}]\n"
                f"지표: {name_en} ({series_id})\n"
                f"최신값: {latest_val}\n"
                f"최근 추이:\n{values_str}\n\n"
                f"이 지표는 투자 판단에 중요한 매크로 경제 신호입니다."
            )
            n = add(text, "macro", "FRED", recent[0][0] if recent else today())
            print(f"  + {name_kr}: {latest_val} ({n}청크)")
        except Exception as e:
            print(f"  {series_id} 오류: {e}")


def _add_builtin_macro():
    """FRED API 키 없을 때 기본 매크로 지식 추가"""
    macro_texts = [
        ("연방기금금리(Federal Funds Rate)", "2024년 연방준비제도는 기준금리를 5.25~5.5%로 유지하다가 2024년 9월부터 인하를 시작했습니다. 금리 인하는 주식시장에 긍정적, 채권 가격 상승 요인입니다."),
        ("인플레이션과 CPI", "소비자물가지수(CPI)가 높을수록 연준은 금리를 올려 인플레이션을 억제합니다. 2024년 CPI는 전년 대비 약 3%대로 안정화 추세입니다."),
        ("VIX 공포지수", "VIX는 시장의 변동성 기대치를 나타냅니다. VIX 20 이하는 안정, 30 이상은 공포 구간입니다. VIX가 높을 때는 방어적 자산 비중을 늘리는 전략이 유효합니다."),
        ("S&P 500 시장 전망", "S&P 500은 2024년 AI 붐과 빅테크 실적 호조로 20% 이상 상승했습니다. 2025년에는 금리 인하 사이클 본격화로 추가 상승 여력이 있으나 밸류에이션 부담이 있습니다."),
        ("암호화폐 시장", "비트코인은 2024년 현물 ETF 승인 후 급등, 2024년 11월 10만 달러를 돌파했습니다. 반감기(2024년 4월) 이후 공급 감소로 장기 상승 압력이 있습니다."),
    ]
    for title, content in macro_texts:
        text = f"[매크로 경제 분석 — {title}]\n\n{content}"
        n = add(text, "macro", "내장 지식베이스", today())
        print(f"  + {title} ({n}청크)")


# ════════════════════════════════════════════════════════
# 4. 투자 전문 지식 (항상 추가)
# ════════════════════════════════════════════════════════
def add_investment_knowledge():
    print("\n[4] 투자 전문 지식 적재 중...")

    knowledge = [
        ("포트폴리오 현대 이론 (MPT)", """
현대 포트폴리오 이론(Modern Portfolio Theory)은 해리 마코위츠가 1952년 제안했습니다.
핵심 원칙: 분산 투자로 같은 기대 수익에서 리스크를 최소화할 수 있습니다.
효율적 프론티어: 주어진 리스크 수준에서 최고 수익을 내는 포트폴리오 집합입니다.
샤프 비율 = (포트폴리오 수익률 - 무위험 수익률) / 포트폴리오 표준편차
샤프 비율이 1.0 이상이면 양호, 2.0 이상이면 우수한 성과로 평가합니다.
        """),
        ("강화학습 PPO 포트폴리오 최적화", """
V-Invest는 PPO(Proximal Policy Optimization) 강화학습으로 포트폴리오를 최적화합니다.
상태(State): 최근 20일간 각 자산의 일별 수익률 변화 패턴
행동(Action): BTC, ETH, SOL, AAPL, NVDA, TSLA, CASH 7개 자산 배분 비율
보상(Reward): 일별 샤프 비율 (수익 / 변동성)
BTC, ETH, SOL은 고위험 고수익, AAPL, NVDA, TSLA는 중위험, CASH는 안전자산입니다.
공포지수(VIX)가 30 이상일 때 CASH 비중을 높이는 방어적 전략을 학습합니다.
        """),
        ("비트코인 투자 분석", """
비트코인(BTC)은 디지털 금으로 불리는 최초의 암호화폐입니다.
총 공급량: 2,100만 개 (희소성 보장)
반감기: 약 4년마다 채굴 보상 반감 → 공급 감소 → 역사적으로 가격 상승
2024년 현물 ETF 승인: 기관 투자자 진입 확대
리스크: 규제 리스크, 변동성 (연간 변동성 약 70%), 거래소 해킹
적합 투자자: 높은 변동성 감내, 장기 보유 가능자
        """),
        ("NVIDIA AI 반도체 투자 분석", """
NVIDIA(NVDA)는 AI 인프라의 핵심 GPU 제조업체입니다.
AI 데이터센터 매출: 2024년 전년 대비 3배 이상 성장
H100, H200, Blackwell GPU: AI 모델 학습/추론에 필수
경쟁사: AMD, Intel, 자체 칩 개발하는 빅테크
리스크: 높은 밸류에이션(PER 35~50배), 대중국 수출 규제
2025년 전망: AI 투자 지속 확대로 수요 견조, 단 경쟁 심화 우려
        """),
        ("테슬라 투자 분석", """
테슬라(TSLA)는 전기차와 에너지 솔루션을 중심으로 하는 기술 기업입니다.
주요 사업: 전기차, 에너지 저장, 태양광, FSD 자율주행, Robotaxi
2024년 납품량: 약 180만 대 (전년 대비 소폭 감소)
리스크: 경쟁 심화(중국 BYD 등), 머스크 이미지 리스크, 마진 압박
성장 동력: FSD 자율주행 상용화, Cybercab Robotaxi, Optimus 로봇
밸류에이션: 미래 성장 프리미엄 포함으로 전통 자동차 대비 높은 PER
        """),
        ("금리와 주식시장 관계", """
금리와 주식시장은 역상관 관계입니다.
금리 인상 → 기업 대출 비용 증가 → 이익 감소 → 주가 하락 압력
금리 인상 → 채권 매력도 상승 → 주식에서 채권으로 자금 이동
금리 인하 → 반대 효과 → 주식시장 상승 요인
특히 성장주(기술주)는 금리에 민감 (미래 현금흐름 현재가치 계산 영향)
가치주(배당주)는 금리 상승기에 상대적으로 방어적
2024~2025년: 연준 금리 인하 사이클 → 성장주에 유리한 환경
        """),
        ("시각장애인 투자 접근성", """
V-Invest는 시각장애인의 금융 정보 접근성을 혁신합니다.
기존 문제: 대부분의 주식 앱이 차트와 시각 정보 중심
V-Invest 해결책:
1. 음성 명령으로 시세 조회 ("비트코인 현재 얼마야?")
2. AI가 차트를 분석해 음성으로 설명 (GPT-4o Vision)
3. PPO AI가 최적 포트폴리오를 음성으로 추천
4. 주요 이벤트 발생시 자동 음성 알림
5. 스크린리더(NVDA, VoiceOver) 완전 호환
이 서비스로 시각장애인도 기관투자자와 동등한 투자 분석 능력을 가질 수 있습니다.
        """),
        ("공포탐욕지수 활용법", """
암호화폐 공포탐욕지수(Fear & Greed Index)는 시장 심리를 0~100으로 나타냅니다.
0~24: 극도의 공포 (Extreme Fear) → 매수 기회 신호
25~49: 공포 (Fear) → 조심스러운 매수
50: 중립 (Neutral)
51~74: 탐욕 (Greed) → 리스크 관리 필요
75~100: 극도의 탐욕 (Extreme Greed) → 과열 신호, 매도 고려
워런 버핏: "남들이 두려워할 때 탐욕스럽게, 남들이 탐욕스러울 때 두려워하라"
V-Invest PPO 모델은 공포지수를 상태(State)의 하나로 활용합니다.
        """),
        ("분산투자 전략", """
효과적인 분산투자 원칙:
1. 자산군 분산: 주식, 채권, 암호화폐, 원자재, 현금
2. 지역 분산: 미국, 한국, 신흥국, 유럽
3. 섹터 분산: IT, 헬스케어, 에너지, 금융, 소비재
4. 시간 분산: 정기 적립식 투자(DCA, Dollar Cost Averaging)
V-Invest PPO 모델의 기본 원칙:
- 단일 자산 최대 30% 이상 배분 방지
- 시장 공포 시 현금 비중 자동 증가
- 강한 상승장에서 위험자산 비중 증가
        """),
        ("AI 투자 분석의 한계와 주의사항", """
AI 투자 분석 서비스 이용 시 주의사항:
1. AI 분석은 참고용이며 투자 결정의 최종 책임은 본인에게 있습니다
2. 과거 데이터 기반 학습이므로 미래를 보장하지 않습니다
3. 블랙스완 이벤트(코로나, 전쟁 등)는 예측 불가합니다
4. 개인의 재무 상황, 투자 기간, 위험 허용도가 다릅니다
5. 금융 전문가의 조언을 병행하는 것을 권장합니다
V-Invest는 시각장애인의 정보 접근성 향상이 목적이며,
투자 수익을 보장하지 않습니다.
        """),
    ]

    for title, content in knowledge:
        text = f"[투자 지식 — {title}]\n{content.strip()}"
        n = add(text, "knowledge", "V-Invest 지식베이스", today())
        print(f"  + {title[:40]} ({n}청크)")


# ════════════════════════════════════════════════════════
# 5. 최근 시장 요약 보고서 생성
# ════════════════════════════════════════════════════════
def add_market_summary():
    print("\n[5] 최근 시장 요약 리포트 생성 중...")

    # Yahoo Finance에서 실시간 데이터 가져와서 리포트 생성
    summary_data = {}
    symbols = {"비트코인": "BTC-USD", "이더리움": "ETH-USD", "솔라나": "SOL-USD",
               "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA",
               "마이크로소프트": "MSFT", "아마존": "AMZN"}

    for name_kr, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
            r   = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            meta = r.json()["chart"]["result"][0]["meta"]
            price  = meta.get("regularMarketPrice", 0)
            prev   = meta.get("chartPreviousClose", price) or price
            change = round((price - prev) / prev * 100, 2) if prev else 0
            summary_data[name_kr] = {"price": price, "change": change, "sym": sym}
        except:
            pass

    if summary_data:
        lines = [f"[{today()} 시장 일일 요약 리포트]\n"]
        for name, d in summary_data.items():
            arrow = "▲" if d["change"] >= 0 else "▼"
            lines.append(f"{name}({d['sym']}): ${d['price']:,.2f}  {arrow}{d['change']:+.2f}%")

        # 공포탐욕지수
        try:
            fg = requests.get("https://api.alternative.me/fng/", timeout=5).json()
            val = fg["data"][0]["value"]
            cls = fg["data"][0]["value_classification"]
            lines.append(f"\n공포탐욕지수: {val}/100 ({cls})")
        except:
            pass

        lines.append(f"\n이 데이터는 {today()} 기준 실시간 시세입니다.")
        text = "\n".join(lines)
        n = add(text, "daily_report", "V-Invest 자동 리포트", today())
        print(f"  + 일일 시장 요약 리포트 ({n}청크)")


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  V-Invest RAG 지식베이스 초기화")
    print(f"  {today()}")
    print("=" * 55)

    before = kb.count
    print(f"\n현재 저장된 문서 수: {before}개")

    fetch_newsapi()
    fetch_yahoo_news()
    fetch_fred()
    add_investment_knowledge()
    add_market_summary()

    after = kb.count
    print(f"\n{'=' * 55}")
    print(f"  완료! {after - before}개 청크 추가 (총 {after}개)")
    print(f"  이제 /rag/chat 엔드포인트에서 실제 데이터 기반 답변 제공")
    print(f"{'=' * 55}")
