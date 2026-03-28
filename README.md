# V-Invest — 시각 장애인을 위한 Voice-Vision AI 투자 어시스턴트

> **기계학습 프로젝트** | PPO 강화학습 + RAG + GPT-4o Vision + n8n 워크플로우 자동화

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [타겟 사용자 및 사회적 가치](#2-타겟-사용자-및-사회적-가치)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [주요 기능](#4-주요-기능)
5. [ML·AI 컴포넌트](#5-mlai-컴포넌트)
6. [데이터 소스](#6-데이터-소스)
7. [API 엔드포인트](#7-api-엔드포인트)
8. [n8n 워크플로우](#8-n8n-워크플로우)
9. [프로젝트 구조](#9-프로젝트-구조)
10. [설치 및 실행](#10-설치-및-실행)
11. [환경 변수](#11-환경-변수)
12. [팀원 협업 가이드](#12-팀원-협업-가이드)

---

## 1. 프로젝트 개요

V-Invest는 **시각 장애인도 혼자서 주식·암호화폐 투자 정보를 얻고 의사결정을 내릴 수 있도록** 설계된 AI 투자 어시스턴트입니다.

| 구분 | 내용 |
|------|------|
| 프론트엔드 | React + Vite + Tailwind CSS (PWA) |
| 백엔드 | Python FastAPI |
| ML 엔진 | PPO 강화학습 (Stable-Baselines3) |
| AI 엔진 | RAG (ChromaDB + LangChain + GPT-4o-mini), GPT-4o Vision |
| 음성 인터페이스 | OpenAI Whisper(STT) + OpenAI TTS |
| 워크플로우 자동화 | n8n (로컬) |
| 실시간 데이터 | Finnhub · Binance · Yahoo Finance · FRED · NewsAPI |

---

## 2. 타겟 사용자 및 사회적 가치

### 왜 시각 장애인인가?

기존 투자 플랫폼(증권사 앱, 트레이딩 뷰 등)은 차트, 그래프, 숫자 테이블 중심으로 설계되어 **시각 장애인이 독립적으로 사용하기 어렵습니다.**

- 국내 시각 장애인 약 25만 명 (2023년 복지부 통계)
- 기존 스크린 리더는 차트·그래프 정보를 읽지 못함
- 금융 정보 접근성 불평등 → 투자 기회 박탈

### V-Invest가 해결하는 것

| 문제 | V-Invest 해결책 |
|------|----------------|
| 차트를 눈으로 봐야만 이해 가능 | GPT-4o Vision이 차트를 분석하여 **음성 설명 생성** |
| 복잡한 금융 용어를 이해하기 어려움 | RAG가 쉬운 한국어로 **맞춤 설명** |
| 매번 직접 정보를 찾아야 함 | n8n + APScheduler가 **1시간마다 자동 리포트 생성** |
| 음성으로 질문하고 싶음 | Whisper STT로 **음성 질문 → AI 답변 → TTS 음성 출력** |

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    프론트엔드 (React PWA)                 │
│  Dashboard │ Portfolio │ Chat(음성Q&A) │ n8n 리포트 패널  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│              백엔드 (FastAPI, port 8000)                  │
│                                                          │
│  /voice    │ STT (Whisper) + TTS (OpenAI)               │
│  /charts   │ GPT-4o Vision — 차트 → 음성 설명            │
│  /rag      │ RAG Q&A (ChromaDB + GPT-4o-mini)           │
│  /portfolio│ PPO 강화학습 포트폴리오 추천                  │
│  /analysis │ AI 분석 파이프라인 (SSE 스트리밍)             │
│  /market-data │ 실시간 시장 데이터                        │
│  /n8n      │ n8n 연동 (Webhook 수신 + SSE 브로드캐스트)   │
└──────┬────────────────────────────────┬─────────────────┘
       │                                │ SSE push
┌──────▼──────────┐          ┌──────────▼──────┐
│  외부 데이터 API │          │  n8n 워크플로우   │
│                 │          │                  │
│ Finnhub  (주식) │          │ 1. 시장 데이터 수집│
│ Binance  (코인) │          │ 2. PPO 추천       │
│ Yahoo Finance   │          │ 3. RAG 분석       │
│ FRED     (매크로)│          │ 4. 리포트 통합    │
│ NewsAPI  (뉴스) │          │ 5. 프론트 전송    │
└─────────────────┘          └──────────────────┘
```

---

## 4. 주요 기능

### 4-1. 실시간 대시보드
- **주식 시세**: AAPL, NVDA, TSLA, MSFT, GOOGL, AMZN, META (Finnhub)
- **암호화폐 시세**: BTC, ETH, SOL, BNB, XRP (Binance)
- **주요 지수**: S&P 500, NASDAQ, DOW Jones, VIX (Yahoo Finance)
- **원자재**: 금, 은, 원유 (Yahoo Finance)
- **차트**: Yahoo Finance 히스토리 기반 인터랙티브 차트 (1M/3M/1Y)
- **경제 이벤트**: FOMC, CPI, NFP 발표일 + Finnhub 실적 발표 캘린더
- **뉴스 피드**: NewsAPI + Finnhub 뉴스 → GPT-4o-mini 한국어 번역

### 4-2. 음성 인터페이스 (시각 장애인 핵심 기능)
- **STT**: 마이크 입력 → OpenAI Whisper → 텍스트 변환
- **TTS**: AI 답변 텍스트 → OpenAI TTS → MP3 스트리밍 재생
- **Web Speech API**: 브라우저 내장 STT/TTS (Whisper 보조)
- 뉴스 헤드라인, n8n 리포트 내용 모두 TTS로 청취 가능

### 4-3. PPO 강화학습 포트폴리오 추천
- 실시간 시장 데이터(최근 20일 수익률)를 입력으로 PPO 모델 추론
- 7개 자산(BTC, ETH, SOL, AAPL, NVDA, TSLA, CASH) 최적 비중 출력
- 공포탐욕지수 연동: 극도의 공포 시 CASH 비중 자동 증가
- TTS 요약: "오늘은 테슬라 22%, 엔비디아 19% 비중을 추천합니다" 형식

### 4-4. RAG 투자 Q&A
- 음성 또는 텍스트로 자유롭게 투자 질문
- ChromaDB에 축적된 리포트·뉴스·거시경제 데이터 기반 답변
- GPT-4o-mini가 TTS 최적화(단위 포함, 300자 이내) 형식으로 답변
- "AAPL 지금 사도 될까요?", "요즘 금리 어떻게 됩니까?" 등 자연어 질의 가능

### 4-5. GPT-4o Vision 차트 분석
- 차트 이미지 URL 또는 파일 업로드 → GPT-4o Vision 분석
- 시각적 표현("보다시피" 등) 제거, 수치 중심 음성 설명 생성
- "AAPL 현재가 248달러, RSI 41로 중립권, 단기 약세" 형식

### 4-6. n8n 자동화 리포트
- 1시간마다 자동 실행 (Schedule 트리거)
- 수동 실행: `http://localhost:5678` → "Test Workflow" 클릭
- 결과가 프론트엔드 알림 패널에 실시간(SSE) 전달
- 알림 클릭 시 전체 리포트 내용 확인 + TTS 읽기 가능

---

## 5. ML·AI 컴포넌트

### 5-1. PPO 강화학습 (Stable-Baselines3)

**학습 데이터**
- Yahoo Finance에서 BTC, ETH, SOL, AAPL, NVDA, TSLA 3년치 일별 주가 다운로드
- 20일 롤링 윈도우 수익률을 관측 벡터(120차원)로 구성

**환경 설계 (`PortfolioEnv`)**
```
관측 공간: Box(120,) — 6개 자산 × 20일 일별수익률
행동 공간: Box(7,)   — 7개 자산 비중 (softmax 정규화)
보상 함수: Sharpe Ratio (수익률 / 변동성)
```

**추론 흐름**
```
Yahoo Finance API (최근 20일 실제 데이터)
    → 120차원 관측 벡터
    → PPO 신경망 (MlpPolicy)
    → Softmax → 자산 비중 딕셔너리
```

**모델 재학습**
```bash
cd backend
python train_ppo.py
```

### 5-2. RAG (Retrieval-Augmented Generation)

**구성 요소**
| 컴포넌트 | 사용 기술 |
|---------|-----------|
| Vector DB | ChromaDB (로컬 저장) |
| Embeddings | OpenAI `text-embedding-3-small` |
| LLM | GPT-4o-mini |
| 프레임워크 | LangChain |

**데이터 시딩 (`seed_rag.py`)**
- NewsAPI 최신 뉴스 기사 (투자·경제 키워드)
- Yahoo Finance 주요 종목 재무 데이터 요약
- FRED 매크로 지표 (금리, CPI, GDP 등)
- 내부 투자 지식 (투자 원칙, 용어 설명)

**질의 흐름**
```
사용자 질문 (STT 텍스트)
    → OpenAI Embedding 벡터화
    → ChromaDB 유사도 검색 (Top 3 청크)
    → GPT-4o-mini에 컨텍스트 주입
    → TTS 최적화 답변 반환
```

**RAG DB 재구축**
```bash
cd backend
python seed_rag.py
```

### 5-3. GPT-4o Vision (차트 분석)

- **입력**: 차트 이미지 URL 또는 base64
- **처리**: GPT-4o Vision API
- **출력**: 시각 장애인용 음성 설명 텍스트
- **프롬프트 전략**: 시각적 표현 금지, 수치·방향·지지선 명시

---

## 6. 데이터 소스

| 데이터 종류 | 출처 | 갱신 주기 | API |
|------------|------|-----------|-----|
| 주식 실시간 시세 | Finnhub | 실시간 | `finnhub.io/api/v1/quote` |
| 암호화폐 시세 | Binance | 실시간 | `api.binance.com/api/v3/ticker` |
| 주가 히스토리 (차트) | Yahoo Finance | 일별 | `query2.finance.yahoo.com` |
| 주요 지수 / 원자재 | Yahoo Finance | 실시간 | `^GSPC, ^IXIC, GC=F, CL=F` |
| 매크로 지표 (금리·GDP) | FRED | 월별 | `api.stlouisfed.org` |
| CPI / PPI | BLS | 월별 | `api.bls.gov` |
| 뉴스 피드 | NewsAPI + Finnhub | 실시간 | `newsapi.org` |
| 공포탐욕지수 | Alternative.me | 일별 | `api.alternative.me` |
| 실적 발표 캘린더 | Finnhub | 분기별 | `finnhub.io/api/v1/calendar/earnings` |

---

## 7. API 엔드포인트

> 전체 인터랙티브 문서: `http://localhost:8000/docs`

### 음성 (Voice)
| Method | URL | 설명 |
|--------|-----|------|
| POST | `/voice/stt` | 오디오 파일 → 텍스트 (Whisper) |
| POST | `/voice/tts` | 텍스트 → MP3 오디오 스트리밍 |

### 차트 분석 (Charts / Vision)
| Method | URL | 설명 |
|--------|-----|------|
| POST | `/charts/analyze` | 이미지 URL/파일 → 음성 설명 텍스트 |
| GET | `/charts/analyze/symbol/{symbol}` | 종목 심볼 → 차트 자동 생성 → 분석 |

### RAG Q&A
| Method | URL | 설명 |
|--------|-----|------|
| POST | `/rag/chat` | 투자 질문 → RAG 답변 |
| GET | `/rag/status` | ChromaDB 상태 조회 |

### PPO 포트폴리오
| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/portfolio/recommend` | PPO 포트폴리오 추천 |
| GET | `/portfolio/backtest` | 백테스트 결과 조회 |

### 시장 데이터
| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/market-data` | 주식(Finnhub) + 코인(Binance) |
| GET | `/market-data/full` | 전체 데이터 (주식·코인·매크로·뉴스) |
| GET | `/market-data/macro` | 매크로 지표 (FRED + BLS) |
| GET | `/market-data/history/{symbol}` | 차트용 히스토리 (Yahoo Finance) |
| GET | `/market-data/events` | 경제 이벤트 캘린더 |
| GET | `/market-data/news/feed/ko` | 뉴스 피드 (한국어 번역) |

### n8n 연동
| Method | URL | 설명 |
|--------|-----|------|
| POST | `/n8n/report` | n8n 워크플로우 → 리포트 수신 |
| GET | `/n8n/stream` | SSE — 프론트엔드 실시간 알림 |

### 기타
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/health` | 서버 상태 + 스케줄러 정보 |
| GET | `/analysis/latest` | 최신 AI 분석 리포트 |
| GET | `/analysis/history` | 리포트 히스토리 목록 |

---

## 8. n8n 워크플로우

### 워크플로우 흐름

```
[트리거] ─────────────────────────────────────────────────────────────────────────►
  ├── 1시간 자동 실행 트리거 (Schedule)
  └── 수동 웹훅 트리거 (POST /webhook/vinvest-trigger)

[1단계] POST http://127.0.0.1:8000/market-data
  → 실시간 주식·코인 시세 수집

[Edit Fields: 시장 데이터 필드 추출]
  btc_price, eth_price, aapl_price, nvda_price, fear_greed, market_raw

[2단계] POST http://127.0.0.1:8000/portfolio/recommend
  → PPO 강화학습 모델로 자산 배분 추천

[Edit Fields: PPO 추천 결과 필드 추출]
  ppo_weights, ppo_voice_summary, ppo_confidence

[3단계] POST http://127.0.0.1:8000/rag/chat
  → RAG AI 시장 분석 (뉴스·거시경제 기반)

[Edit Fields: RAG 분석 결과 필드 추출]
  rag_answer, rag_sources

[4단계] Code 노드 — AI 리포트 통합 생성
  → 시장 데이터 + PPO 추천 + RAG 분석 → 종합 리포트 텍스트 생성

[5단계] POST http://127.0.0.1:8000/n8n/report
  → 백엔드로 리포트 전송 → SSE로 프론트엔드에 실시간 브로드캐스트
```

### 워크플로우 임포트
```bash
n8n import:workflow --input=n8n_workflow.json
```

### GET vs POST 사용 이유
- **POST 사용**: 2단계(PPO), 3단계(RAG)는 외부 서비스가 호출하는 엔드포인트로 데이터를 명시적으로 전송하는 POST가 적합
- **보안**: 민감한 API 키, 분석 요청이 URL에 노출되지 않음
- **REST 관행**: 데이터 수집/변환을 유발하는 요청은 POST로 처리

---

## 9. 프로젝트 구조

```
v-invest/
├── README.md
├── .gitignore
├── n8n_workflow.json          # n8n 워크플로우 정의
│
├── backend/
│   ├── requirements.txt       # Python 의존성
│   ├── .env                   # API 키 (팀원 공유 불가 — 개별 발급)
│   ├── train_ppo.py           # PPO 모델 학습 스크립트
│   ├── seed_rag.py            # ChromaDB 데이터 시딩
│   │
│   ├── models/
│   │   ├── ppo_portfolio.zip  # 학습된 PPO 모델
│   │   └── training_result.json
│   │
│   └── app/
│       ├── main.py            # FastAPI 앱 진입점 + APScheduler
│       │
│       ├── core/
│       │   ├── config.py      # 설정 (API 키, 경로, 파라미터)
│       │   └── llm_client.py  # OpenAI / Gemini 클라이언트
│       │
│       ├── api/
│       │   ├── voice.py       # STT (Whisper) + TTS
│       │   ├── charts.py      # GPT-4o Vision 차트 분석
│       │   ├── rag.py         # RAG Q&A
│       │   ├── portfolio.py   # PPO 포트폴리오 추천
│       │   ├── market.py      # 실시간 시장 데이터
│       │   ├── analysis.py    # AI 분석 파이프라인
│       │   └── n8n.py         # n8n Webhook + SSE 브로드캐스트
│       │
│       ├── services/
│       │   ├── market_data.py       # 외부 API 데이터 수집
│       │   ├── rag_service.py       # ChromaDB + LangChain
│       │   ├── data_collector.py    # 시장 상태 통합 수집
│       │   └── analysis_pipeline.py # AI 분석 파이프라인
│       │
│       └── models/
│           └── ppo_agent.py   # PPO 에이전트 래퍼
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    │
    └── src/
        ├── App.jsx            # 루트 컴포넌트, SSE 연결, 알림 패널
        ├── main.jsx
        ├── index.css
        ├── service-worker.js  # PWA 서비스 워커
        │
        ├── pages/
        │   ├── Dashboard.jsx  # 실시간 시장 대시보드
        │   ├── Portfolio.jsx  # PPO 포트폴리오 페이지
        │   └── Chat.jsx       # 음성 Q&A 채팅
        │
        ├── components/
        │   ├── AudioPlayer.jsx      # 오디오 재생 컴포넌트
        │   ├── HighContrastChart.jsx # 접근성 차트
        │   ├── PipelineStatus.jsx   # 분석 파이프라인 상태
        │   └── VoiceInput.jsx       # 음성 입력 UI
        │
        └── hooks/
            ├── useSpeechToText.js   # Web Speech API STT 훅
            └── useTextToSpeech.js   # TTS 훅
```

---

## 10. 설치 및 실행

### 사전 요구사항
- Python 3.10+
- Node.js 18+
- n8n (전역 설치)

### 1단계: 의존성 설치

```bash
# 백엔드
cd backend
python -m pip install -r requirements.txt

# 프론트엔드
cd frontend
npm install

# n8n (최초 1회)
npm install -g n8n
```

### 2단계: 환경 변수 설정

`backend/.env` 파일 생성:
```env
OPENAI_API_KEY=sk-...
FINNHUB_API_KEY=...
FRED_API_KEY=...
NEWS_API_KEY=...
```

### 3단계: ML 모델 초기화 (최초 1회)

```bash
cd backend

# PPO 모델 학습 (약 3-5분)
python train_ppo.py

# ChromaDB 데이터 시딩 (약 2-3분)
python seed_rag.py
```

### 4단계: 서버 실행

**터미널 1 — 백엔드**
```bash
cd backend
$env:PYTHONIOENCODING="utf-8"
uvicorn app.main:app --port 8000 --reload
```

**터미널 2 — 프론트엔드**
```bash
cd frontend
npm run dev
```

**터미널 3 — n8n**
```bash
n8n start
# 접속: http://localhost:5678
```

### 5단계: n8n 워크플로우 설정

```bash
# 워크플로우 임포트
n8n import:workflow --input=n8n_workflow.json
```

n8n UI(`http://localhost:5678`) → 워크플로우 활성화(toggle ON) → "Test Workflow" 클릭

### 접속 URL

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| 백엔드 API | http://localhost:8000 |
| API 문서 (Swagger) | http://localhost:8000/docs |
| n8n UI | http://localhost:5678 |

---

## 11. 환경 변수

| 변수명 | 용도 | 발급처 |
|--------|------|--------|
| `OPENAI_API_KEY` | GPT-4o, Whisper, TTS, Embeddings | [platform.openai.com](https://platform.openai.com) |
| `FINNHUB_API_KEY` | 주식 실시간 시세, 실적 캘린더 | [finnhub.io](https://finnhub.io) |
| `FRED_API_KEY` | 매크로 경제 지표 | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `NEWS_API_KEY` | 뉴스 피드 | [newsapi.org](https://newsapi.org) |

> `.env` 파일은 `.gitignore`에 등록되어 있어 GitHub에 업로드되지 않습니다.  
> 팀원 각자 위 사이트에서 개인 API 키를 발급받아야 합니다.

---

## 12. 팀원 협업 가이드

### 저장소 클론

```bash
git clone https://github.com/kts6450/v-invest.git
cd v-invest
```

### 최신 변경사항 받기

```bash
git pull origin main
```

### n8n 워크플로우 공유

팀원에게 전달할 파일: **`n8n_workflow.json`** (루트 디렉토리)

```bash
# 팀원이 워크플로우 임포트
n8n import:workflow --input=n8n_workflow.json
```

---

*Built with ❤️ for accessibility — V-Invest Team*
