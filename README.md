# 📈 ETF 스마트 어드바이저 (ETF Smart Advisor)

> **금융 특화 AI 기반 ETF 투자 상담 서비스**
> RAG(검색 증강 생성) 기술과 5단계 컴플라이언스(보안/리스크 통제) 파이프라인이 결합된 AI 챗봇 에이전트 프로젝트입니다.

---

## 🌟 핵심 기능 및 차별점

### 1. 사용자 지식 수준별 맞춤형 응답 (Adaptive Prompting)
- **초급 투자자 모드**: 쉬운 금융 용어 해설, 직관적인 비유와 예시 중심의 친절한 설명 제공.
- **고급 투자자 모드**: NAV, 추적오차, TER, 샤프지수 등 전문 금융 용어 및 정량적 데이터, 포트폴리오 리밸런싱/세무 최적화 등 심층 분석 제공.

### 2. 고성능 RAG (Retrieval-Augmented Generation) 엔진
- **PDF 지식 베이스 기반**: ETF 공시 및 FAQ 문서를 다단계 청킹(`chunk_size=500`, `chunk_overlap=150`)하여 벡터화.
- **MMR (Maximal Marginal Relevance) 검색**: 상위 결과의 중복 청크를 방지하고 답변의 다양성과 관련성 동시 확보.
- **체인 분리 캐싱**: 사용자 레벨 전환 시 임베딩 재생성 없이 프롬프트+LLM 체인만 교체하여 비용 및 지연 시간 최소화.

### 3. 금융 컴플라이언스 및 5단계 가드레일 (Security & Compliance)
- 🛡️ **입력 필터**: 프롬프트 인젝션 공격 사전에 검지 및 비금융 잡담 질문 차단 (인사말 예외 처리).
- 🔒 **PII 마스킹**: 주민등록번호 등 개인식별정보 정규식 패턴 자동 검출 및 `[마스킹]` 전환.
- ⚖️ **답변 검증**: 불완전판매 위반 표현(단정적 수익 보장 표현) 감지 및 투자 유의사항 고지문 자동 결합.
- 📄 **출처 명시**: 답변 하단에 근거 문서명과 정확한 페이지 번호(`p.N`) 자동 표시.
- 📋 **감사 로그(Audit Trail)**: 입력/출력 검증 기록 세션 관리 및 CSV 다운로드 기능 제공.

---

## 🏗️ 시스템 아키텍처 및 클라우드 배포

```
[ 사용자 (Browser) ]
       │
       ▼
[ Amazon API Gateway (HTTPS 관문 / Rate Limiting) ]
       │
       ▼
[ AWS ECS Fargate (Serverless Container 실행 엔진) ]
       ├── Streamlit (UI Framework)
       ├── LangChain (RAG Orchestration)
       ├── FAISS (Vector Store)
       └── Gemini 2.5 Flash (LLM)
       │
       ▼
[ Amazon CloudWatch (실시간 로그 수집 & 모니터링) ]
```

---

## 📁 프로젝트 구조

```text
3주차_프로토타입_김동성/
├── app.py              # Streamlit 메인 UI 및 세션/감사로그 관리
├── rag_module.py       # FAISS 벡터스토어 생성 및 MMR RAG 체인 로직
├── compliance.py       # PII 마스킹, 인젝션 방어, 컴플라이언스 검증 모듈
├── create_etf_data.py  # ETF FAQ 데이터 텍스트 기반 PDF 자동 생성기
├── Dockerfile          # 멀티스테이지 도커 컨테이너 빌드 파일 (linux/amd64)
├── .dockerignore       # 도커 빌드 시 보안/캐시 제외 설정
├── .gitignore          # 깃허브 보안 키(.env) 유출 방지 설정
├── requirements.txt    # 버전이 고정된 파이썬 의존성 패키지 목록
└── data/
    └── etf_faq.pdf     # 챗봇 기본 탑재 ETF FAQ 지식 베이스 문서
```

---

## 🚀 로컬 실행 방법

1. **저장소 클론 및 이동**
   ```bash
   git clone <your-repository-url>
   cd 3주차_프로토타입_김동성
   ```

2. **환경변수 설정 (`.env`)**
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

3. **패키지 설치 및 앱 실행**
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
