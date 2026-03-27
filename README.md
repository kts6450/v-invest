# V-Invest — 시각 장애인을 위한 Voice-Vision AI 투자 어시스턴트

> "보는 투자에서 **듣는 투자**로" — 음성과 이미지 AI로 정보 평등을 실현합니다.

---

## 🎯 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 대상 | 시각 장애인 / 저시력 투자자 |
| 핵심 기술 | Vision AI (GPT-4o), Voice STT/TTS, PPO 강화학습, RAG |
| 차별점 | 차트 이미지를 AI가 분석 → 음성으로 설명 (기존 앱 최초) |
| 발표 주제 | ML API를 Web Server로 서비스하고 n8n과 연동 |

---

## 📋 발표 주제 대응

| 발표 요구사항 | 구현 방법 | 담당 파일 |
|--------------|-----------|----------|
| **ML API를 Web Server 통해 서비스** | FastAPI가 AI 분석, RAG, PPO, Vision 등을 REST API로 제공 | `backend/app/api/` 전체 |
| **n8n에 연결해서 ML API 활용** | n8n 워크플로우가 FastAPI ML API 3개를 HTTP 노드로 순서대로 호출 | `n8n-workflow.json` |

### n8n → FastAPI ML API 호출 흐름

```
n8n 스케줄 트리거 (1시간마다)
        │
        ▼
【ML API①】POST /analysis/run-sync   ← 투자분석가 + 리스크 + 편집장 AI
        │           (timeout: 3분)
        │
  ┌─────┴─────┐
  ▼           ▼
【ML API②】          【ML API③】
GET /portfolio/recommend   POST /rag/chat
PPO 강화학습 추론          RAG 과거 리포트 참조
        │
        ▼
n8n Code 노드: ML API 3개 결과 통합
        │
        ├─ 긴급 알림 조건? (심리점수 ±30, VIX>30)
        │
        ▼
POST /reports/save  →  웹UI 실시간 표시 (SSE)
```

---

## 🏗️ 아키텍처 다이어그램

```
[프론트엔드 React PWA]          [백엔드 FastAPI]            [외부 서비스]
         │                              │
         │──POST /voice/stt──────────►│── OpenAI Whisper ──► 텍스트
         │◄──텍스트──────────────────  │
         │                              │
         │──POST /charts/analyze/url──►│── GPT-4o Vision ──► 차트 설명
         │◄──음성 설명 텍스트──────────│
         │                              │
         │──POST /rag/chat────────────►│── ChromaDB 검색
         │                              │── GPT-4o-mini ──►  답변
         │◄──답변 텍스트───────────────│
         │                              │
         │──GET /portfolio/recommend──►│── PPO 모델 추론 ──► 비중
         │◄──자산 배분 + 음성 요약──── │
         │                              │
         │──EventSource /n8n/stream───►│◄── n8n POST /n8n/report
         │◄──SSE 실시간 리포트──────── │
         │                              │
         │──POST /voice/tts───────────►│── OpenAI TTS ──────► MP3
         │◄──MP3 스트리밍──────────────│
                                        │
                                        ├── Finnhub (주식 실시간)
                                        ├── Binance WS (코인 실시간)
                                        └── FRED API (매크로)
```

---

## 📂 폴더 구조

```
v-invest/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 앱 + 라이프사이클
│   │   ├── core/
│   │   │   ├── config.py         # 환경 변수 (API 키, 경로)
│   │   │   └── llm_client.py     # OpenAI/Gemini 클라이언트 팩토리
│   │   ├── api/
│   │   │   ├── charts.py         # ★ Vision 에이전트: 차트→음성설명
│   │   │   ├── voice.py          # STT(Whisper) / TTS(OpenAI)
│   │   │   ├── portfolio.py      # PPO 포트폴리오 최적화
│   │   │   ├── rag.py            # RAG 투자 Q&A
│   │   │   └── n8n.py            # n8n 리포트 수신 + SSE 브로드캐스트
│   │   ├── services/
│   │   │   ├── data_collector.py # Binance WebSocket + Finnhub 폴링
│   │   │   └── rag_service.py    # ChromaDB + LangChain RAG 체인
│   │   └── models/
│   │       └── ppo_agent.py      # PPO 추론 래퍼 + PortfolioEnv
│   └── requirements.txt
│
└── frontend/
    ├── public/
    │   └── manifest.json         # PWA 설정
    └── src/
        ├── App.js                # 루트 (하단 탭 네비게이션)
        ├── hooks/
        │   ├── useSpeechToText.js  # Web Speech API + Whisper fallback
        │   └── useTextToSpeech.js  # Web Speech Synthesis + OpenAI TTS
        ├── components/
        │   ├── VoiceInput.jsx      # 터치/음성 입력 (전체화면 터치 지원)
        │   ├── AudioPlayer.jsx     # 접근성 오디오 플레이어 (키보드 제어)
        │   └── HighContrastChart.jsx # Vision AI 연동 고대비 차트
        ├── pages/
        │   ├── Dashboard.jsx     # 실시간 가격 + 차트 + SSE 리포트 알림
        │   ├── Chat.jsx          # 음성 RAG Q&A 채팅
        │   └── Portfolio.jsx     # PPO 추천 + 백테스트
        └── service-worker.js     # PWA 오프라인 캐싱 + 푸시 알림
```

---

## 🤖 ML/AI 구성 요소

| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| **Vision 에이전트** | GPT-4o Vision | 차트 이미지 → 시각 장애인 맞춤 음성 설명 |
| **STT** | Web Speech API / OpenAI Whisper | 음성 질문 → 텍스트 변환 |
| **TTS** | Web Speech Synthesis / OpenAI TTS | 텍스트 → 자연스러운 음성 |
| **RAG** | ChromaDB + LangChain + GPT-4o-mini | 금융 리포트 기반 Q&A |
| **PPO** | Stable-Baselines3 | 자산 배분 강화학습 최적화 |
| **멀티에이전트** | n8n + Gemini | 투자분석가 + 리스크 전문가 AI 파이프라인 |

---

## 🚀 실행 방법

### 백엔드

```bash
cd v-invest/backend
pip install -r requirements.txt

# .env 파일 생성
echo "OPENAI_API_KEY=sk-..." > .env
echo "FINNHUB_API_KEY=..."  >> .env
echo "FRED_API_KEY=..."     >> .env

uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```bash
cd v-invest/frontend
npm install
npm start          # http://localhost:3000
# PWA 빌드
npm run build
```

### n8n 연동

1. n8n에서 기존 워크플로우의 마지막 노드(리포트 포맷팅) 이후에
   **HTTP Request 노드** 추가
2. `POST http://localhost:8000/n8n/report` 로 전송
3. Body: `{ content, sentimentScore, sentimentLabel, grade }`

---

## ♿ 접근성 기능 목록

| 기능 | 구현 방식 |
|------|-----------|
| 음성 입력 | Web Speech API (한국어 KR) |
| 음성 출력 | OpenAI TTS nova 목소리 / Web Speech Synthesis |
| 차트 음성 설명 | GPT-4o Vision → TTS 자동 재생 |
| 전체 화면 터치 | `onPointerDown` 이벤트 (작은 버튼 찾기 불필요) |
| 스크린 리더 | ARIA live regions + aria-label + role 속성 |
| 키보드 탐색 | 차트 데이터 포인트 ←/→ 탐색, Space 재생 |
| 촉각 피드백 | `navigator.vibrate()` (녹음 시작/종료) |
| 고대비 모드 | WCAG AA 기준 4.5:1 이상 대비율 |
| 모션 감소 | `prefers-reduced-motion` CSS 미디어 쿼리 |
| 알림 | PWA Push Notification (진동 패턴 포함) |

---

## 📡 주요 API 엔드포인트

```
POST /voice/stt              음성 파일 → 텍스트 (Whisper)
POST /voice/tts              텍스트 → MP3 스트리밍
POST /charts/analyze/upload  차트 이미지 파일 → 음성 설명
POST /charts/analyze/url     차트 URL → 음성 설명
POST /rag/chat               음성 Q&A (RAG 기반)
POST /rag/add-report         리포트 벡터 DB 저장
GET  /portfolio/recommend    PPO 포트폴리오 추천
GET  /portfolio/backtest     백테스트 성과
POST /n8n/report             n8n 리포트 수신
GET  /n8n/stream             SSE 실시간 스트리밍
GET  /health                 서버 상태
```

---

## 🗓️ 주차별 개발 계획

| 주차 | 목표 | 핵심 ML |
|------|------|---------|
| 현재 | 골격 완성, RAG 동작 확인 | RAG (ChromaDB) |
| +1주 | Vision 에이전트 실제 동작 | GPT-4o Vision |
| +2주 | PPO 모델 학습 + 백테스트 | Stable-Baselines3 |
| +3주 | PWA 빌드 + 푸시 알림 | 서비스 워커 |
| 최종 | 전체 통합 데모 | 멀티 AI 파이프라인 |
