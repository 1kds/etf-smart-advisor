"""
RAG 모듈 (rag_module.py)
========================
제안서 슬라이드 2~3의 핵심 기능을 구현

- NLU: 자연어 질문 분석 및 의도 분류
- Retrieval: Vector DB를 통한 고속 시맨틱 검색 (MMR 방식)
- NLG: 금융 도메인 sLLM 기반 고품질 답변 생성
  → 사용자 지식 수준별(초급/고급) 맞춤형 설명
  → 출처(공시 등) 명시

[3주차 개선]
- create_vectorstore() / build_rag_chain() 분리
  → 레벨 전환 시 벡터스토어 재생성 없이 프롬프트+LLM만 교체
- MMR 검색 방식 도입: 상위 k개 중복 청크 방지
- 레벨별 k값 차등: 고급=7, 초급=5
"""

import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# .env 파일에 저장된 API 키 로드
load_dotenv()


# ============================================================
# 금융 전문가 시스템 프롬프트 (제안서 슬라이드 2: NLG)
# - "금융 도메인 sLLM 기반 고품질 텍스트 생성"
# - "사용자 지식 수준별(초급/고급) 맞춤형 설명"
# - "가독성 높은 포맷 및 출처(공시 등) 명시"
# ============================================================

SYSTEM_PROMPT_BEGINNER = """당신은 "ETF 스마트 어드바이저"라는 이름의 금융 투자 전문 AI 상담사입니다.
증권사에서 운영하는 공식 ETF 투자 상담 서비스를 담당하고 있습니다.

[현재 사용자 설정: 초급 투자자]
사용자는 투자 경험이 적은 초급 투자자입니다. 다음 원칙에 따라 답변하세요:

1. 금융 용어를 사용할 때는 반드시 쉬운 말로 풀어서 설명해주세요
   - 예시: "NAV(순자산가치, 쉽게 말해 ETF 한 주의 실제 가치)"
2. 비유와 예시를 적극적으로 활용하세요
   - 예시: "분산투자는 '달걀을 여러 바구니에 나누어 담는 것'과 같습니다"
3. 복잡한 계산이나 수식보다는 핵심 개념 위주로 설명하세요
4. 초보 투자자가 반드시 알아야 할 주의사항을 강조하세요

[답변 규칙]
- 반드시 아래 제공된 문서 내용(Context)만을 근거로 답변하세요
- 문서에 없는 내용은 "해당 정보는 현재 보유한 문서에서 확인할 수 없습니다"라고 솔직하게 말하세요
- 답변 마지막에 참고한 문서의 출처 정보를 "[📄 출처]" 형태로 명시하세요
- 투자를 단정적으로 권유하는 표현(예: "반드시 오릅니다", "확실한 수익")은 절대 사용하지 마세요
- 답변은 한국어로 작성하세요

---
[참고 문서 (Context)]
{context}
---

사용자 질문: {question}

답변:"""

SYSTEM_PROMPT_ADVANCED = """당신은 "ETF 스마트 어드바이저"라는 이름의 금융 투자 전문 AI 상담사입니다.
증권사에서 운영하는 공식 ETF 투자 상담 서비스를 담당하고 있습니다.

[현재 사용자 설정: 고급 투자자]
사용자는 투자 경험이 풍부한 고급 투자자입니다. 다음 원칙에 따라 답변하세요:

1. 전문 금융 용어를 자유롭게 사용해도 됩니다 (NAV, 추적오차, TER, 샤프지수 등)
2. 정량적 데이터와 구체적인 수치를 포함하여 답변하세요
3. 기술적 분석이나 심층적인 비교 분석이 가능합니다
4. 포트폴리오 구성, 리밸런싱, 세금 최적화 등 고급 전략을 다룰 수 있습니다
5. 관련 규제나 세제 혜택 등 실무적인 정보를 포함하세요

[답변 규칙]
- 반드시 아래 제공된 문서 내용(Context)만을 근거로 답변하세요
- 문서에 없는 내용은 "해당 정보는 현재 보유한 문서에서 확인할 수 없습니다"라고 솔직하게 말하세요
- 답변 마지막에 참고한 문서의 출처 정보를 "[📄 출처]" 형태로 명시하세요
- 투자를 단정적으로 권유하는 표현(예: "반드시 오릅니다", "확실한 수익")은 절대 사용하지 마세요
- 답변은 한국어로 작성하세요

---
[참고 문서 (Context)]
{context}
---

사용자 질문: {question}

답변:"""


# ============================================================
# 컨텍스트 포맷터
# - FAISS 내부 UUID 대신 "파일명 + 페이지" 형태로 태깅
# ============================================================
def format_docs(docs):
    """검색된 문서 청크를 LLM이 읽기 좋은 형태로 포맷팅합니다."""
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = os.path.basename(doc.metadata.get("source", "알 수 없음"))
        # [3주차 개선 5] PyMuPDFLoader는 0-indexed → 사용자에게는 +1 표시
        page = doc.metadata.get("page", 0)
        page_display = page + 1 if isinstance(page, int) else page
        formatted.append(
            f"[문서 {i} | 출처: {source}, p.{page_display}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(formatted)


# ============================================================
# [3주차 개선 1] 벡터스토어 생성 함수 (문서가 바뀔 때만 호출)
# ============================================================
def create_vectorstore(pdf_path: str):
    """
    PDF 문서를 로드하고 FAISS 벡터스토어를 생성합니다.

    레벨 전환 시에는 이 함수를 재호출하지 않고,
    build_rag_chain()만 재호출하여 임베딩 비용을 절감합니다.

    Args:
        pdf_path: PDF 문서 경로

    Returns:
        FAISS 벡터스토어 객체
    """
    # ─── [1단계] 문서 로드 (Document Load) ───
    loader = PyMuPDFLoader(pdf_path)
    docs = loader.load()

    # ─── [2단계] 문서 분할 (Text Split) ───
    # - chunk_size 500: 금융 용어 설명이 보통 한 문단 정도
    # - chunk_overlap 150: 문맥 유지를 위해 넉넉한 오버랩
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    split_documents = text_splitter.split_documents(docs)

    # ─── [3~4단계] 임베딩 및 벡터 DB 저장 ───
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = FAISS.from_documents(documents=split_documents, embedding=embeddings)

    return vectorstore


# ============================================================
# [3주차 개선 1] RAG 체인 생성 함수 (레벨 전환 시 호출)
# [3주차 개선 6] MMR 검색 방식 + 레벨별 k값 차등
# ============================================================
def build_rag_chain(vectorstore, user_level: str = "beginner"):
    """
    벡터스토어에서 RAG 체인을 생성합니다.

    레벨 전환 시 벡터스토어 재생성 없이 프롬프트+LLM 체인만 교체합니다.

    [3주차 개선 6] MMR(Maximal Marginal Relevance) 검색:
    - 관련성이 높으면서도 서로 중복되지 않는 문서 청크를 검색
    - 고급 투자자는 더 넓은 맥락이 필요하므로 k=7, 초급은 k=5

    Args:
        vectorstore: FAISS 벡터스토어
        user_level: "beginner" 또는 "advanced"

    Returns:
        (rag_chain, retriever) 튜플
    """
    # ─── [5단계] 검색기(Retriever) 생성 ───
    # [3주차 개선 6] MMR 방식 + 레벨별 k값 차등
    k_value = 7 if user_level == "advanced" else 5
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k_value,
            "fetch_k": k_value * 3,  # MMR 계산을 위해 후보군 확대
            "lambda_mult": 0.7       # 관련성 70% + 다양성 30% 균형
        }
    )

    # ─── [6~7단계] 프롬프트 및 LLM 설정 ───
    if user_level == "advanced":
        template = SYSTEM_PROMPT_ADVANCED
    else:
        template = SYSTEM_PROMPT_BEGINNER

    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    # ─── [8단계] 체인 생성 (Chain) ───
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain, retriever


# ============================================================
# 하위 호환성을 위한 래퍼 함수
# ============================================================
def create_rag_chain(pdf_path: str, user_level: str = "beginner"):
    """기존 인터페이스 유지용 래퍼. 내부적으로 두 함수를 순서대로 호출합니다."""
    vectorstore = create_vectorstore(pdf_path)
    return build_rag_chain(vectorstore, user_level)