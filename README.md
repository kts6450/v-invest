# V-Invest — 시각 장애인을 위한 Voice-Vision AI 투자 어시스턴트

> "보는 투자에서 **듣는 투자**로" — 음성과 AI로 금융 정보 격차를 해소합니다.

---

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 대상 | 시각 장애인 / 저시력 투자자 |
| 핵심 기술 | PPO 강화학습, RAG, GPT-4o Vision, TTS/STT, n8n 자동화 |
| 발표 주제 | **ML API를 Web Server로 서비스 + n8n 워크플로우 연동** |

---

## n8n 워크플로우 흐름

```
[트리거] 1시간 자동 or 수동 웹훅
         │
         ▼
1단계: POST /market-data        ← Finnhub(주식) + Binance(코인) 실시간 시세
         │
         ▼
2단계: POST /portfolio/recommend ← PPO 강화학습 모델 추론 → 최적 자산 배분
         │
         ▼
3단계: POST /rag/chat            ← ChromaDB 검색 + GPT-4o-mini 시장 분석
         │
         ▼
4단계: n8n Code 노드             ← 1~3단계 결과를 하나의 리포트로 통합
         │
         ▼
5단계: POST /n8n/report          ← 백엔드 저장 + SSE로 브라우저 실시간 표시
```

---

## 데이터 소스

| 분류 | API | 수집 데이터 |
|------|-----|------------|
| 주식 | **Finnhub** | AAPL, NVDA, TSLA, MSFT, GOOGL, AMZN, META 실시간 시세 |
| 암호화폐 | **Binance REST** | BTC, ETH, SOL, XRP, DOGE 실시간 시세 |
| 거시경제 | **FRED API** | 금리, 실업률, 국채 스프레드 |
| 물가 | **BLS API** | CPI, PPI |
| 지수/원자재 | **Yahoo Finance** | S&P500, NASDAQ, 다우존스, 금, 유가 |
| 뉴스 | **NewsAPI + Finnhub** | Reuters, Bloomberg, CNBC (GPT 한국어 번역) |
| 소셜 | **Reddit** | r/wallstreetbets, r/CryptoCurrency |

---

## ML/AI 구성 요소

| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| **PPO 강화학습** | Stable-Baselines3 | 6개 자산 × 20일 수익률 → 최적 포트폴리오 배분 |
| **RAG** | ChromaDB + LangChain + GPT-4o-mini | 뉴스/리포트 벡터 검색 → 근거 기반 답변 |
| **Vision AI** | GPT-4o Vision | 차트 이미지 → 시각장애인 맞춤 음성 설명 |
| **STT** | OpenAI Whisper | 음성 질문 → 텍스트 변환 |
| **TTS** | OpenAI TTS + Web Speech | 텍스트 → 자연스러운 음성 출력 |
| **뉴스 번역** | GPT-4o-mini | 영문 금융 뉴스 → 한국어 실시간 번역 |

---

## 폴더 구조

```
v-invest/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 앱 진입점
│   │   ├── api/
│   │   │   ├── market.py         # 시장 데이터 (Finnhub + Binance + Yahoo)
│   │   │   ├── portfolio.py      # PPO 포트폴리오 추천/백테스트
│   │   │   ├── rag.py            # RAG 투자 Q&A
│   │   │   ├── charts.py         # Vision AI 차트 분석
│   │   │   ├── voice.py          # STT/TTS
│   │   │   ├── n8n.py            # n8n 리포트 수신 + SSE 브로드캐스트
│   │   │   └── analysis.py       # AI 분석 파이프라인
│   │   ├── models/
│   │   │   └── ppo_agent.py      # PPO 모델 래퍼 (추론)
│   │   └── services/
│   │       ├── market_data.py    # Finnhub/Binance/FRED/BLS/NewsAPI/Reddit
│   │       └── rag_service.py    # ChromaDB + LangChain
│   ├── train_ppo.py              # PPO 모델 학습 스크립트
│   ├── seed_rag.py               # ChromaDB 초기 데이터 주입
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── App.jsx               # 루트 (n8n SSE 연결, 알림 패널)
│       ├── pages/
│       │   ├── Dashboard.jsx     # 실시간 대시보드 + 뉴스 피드 + 경제 캘린더
│       │   ├── Chat.jsx          # 음성 RAG Q&A
│       │   └── Portfolio.jsx     # PPO 포트폴리오 + 백테스트
│       └── hooks/
│           ├── useSpeechToText.js
│           └── useTextToSpeech.js
│
└── n8n_workflow.json             # n8n 워크플로우 (import 파일)
```

---

## 실행 방법

### 1. 백엔드

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 패키지 설치
pip install -r requirements.txt

# .env 파일 생성 (아래 키 필요)
# OPENAI_API_KEY=sk-...
# FINNHUB_API_KEY=...
# FRED_API_KEY=...
# BLS_API_KEY=...
# NEWS_API_KEY=...

# 서버 실행
uvicorn app.main:app --port 8000
```

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

### 3. n8n 워크플로우

```bash
# n8n 설치 (최초 1회)
npm install -g n8n

# 워크플로우 import
n8n import:workflow --input=n8n_workflow.json

# n8n 실행
n8n start            # http://localhost:5678
```

n8n 접속 후 워크플로우 **Activate** → **Execute workflow** 버튼으로 실행

---

## 주요 API 엔드포인트

```
POST /market-data                실시간 시세 (Finnhub + Binance)
GET  /market-data/history/{sym}  가격 히스토리 (차트용)
GET  /market-data/events         경제 이벤트 캘린더 (실적 + FOMC/CPI/NFP)
GET  /market-data/news/feed/ko   한국어 번역 뉴스 피드

POST /portfolio/recommend        PPO 포트폴리오 추천
GET  /portfolio/backtest         백테스트 결과

POST /rag/chat                   RAG AI 투자 Q&A

POST /n8n/report                 n8n 리포트 수신 + SSE 전송
GET  /n8n/stream                 SSE 실시간 스트림 (브라우저 연결)

POST /voice/stt                  음성 → 텍스트 (Whisper)
POST /voice/tts                  텍스트 → 음성 (OpenAI TTS)
GET  /charts/analyze/symbol/{s}  차트 자동 생성 + Vision AI 분석
```

---

## 접근성 기능

| 기능 | 구현 방식 |
|------|-----------|
| 음성 입력 | Web Speech API (한국어) + OpenAI Whisper |
| 음성 출력 | OpenAI TTS / Web Speech Synthesis |
| 차트 음성 설명 | GPT-4o Vision → TTS 자동 재생 |
| 스크린 리더 | ARIA live regions + aria-label |
| 키보드 탐색 | 전체 키보드 접근 가능 |
| 고대비 모드 | WCAG AA 기준 4.5:1 대비율 |
| 모션 감소 | prefers-reduced-motion 지원 |
| n8n 리포트 알림 | SSE 실시간 수신 + TTS 자동 낭독 |
