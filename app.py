"""
ETF 스마트 어드바이저 - 메인 앱 (app.py)
=========================================
제안서 전체 슬라이드를 반영한 ETF 전문 AI 챗봇 프로토타입

아키텍처 흐름:
  사용자 입력 → [입력 필터] → [PII 마스킹] → [RAG 체인] → [답변 검증] → 화면 출력

[3주차 개선]
- [개선 1] 벡터스토어/체인 분리: 레벨 전환 시 임베딩 재생성 방지
- [개선 2] 임시 파일 누수 방지: session_state에 tmp_path 캐싱
- [개선 3] 감사 로그 UI: 사이드바 하단 로그 뷰 + CSV 다운로드
- [개선 4] 에러 로그 출력: 서버 콘솔에 실제 에러 내용 기록
- [개선 5] 페이지 번호 +1: rag_module.py format_docs에서 처리
"""

import streamlit as st
import os
import tempfile
import atexit
import csv
import io
from datetime import datetime
from rag_module import create_vectorstore, build_rag_chain
from compliance import (
    validate_input,
    validate_response,
    get_fallback_response,
    create_compliance_log,
    INVESTMENT_DISCLAIMER,
)

# ============================================================
# 페이지 기본 설정
# ============================================================
st.set_page_config(
    page_title="ETF 스마트 어드바이저",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 커스텀 CSS (ETF 금융 브랜딩)
# ============================================================
st.markdown("""
<style>
    /* 전체 배경 */
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1117 100%);
    }
    
    /* 사이드바 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1629 0%, #1a2332 100%);
        border-right: 1px solid #2d3748;
    }
    
    /* ──── 전체 텍스트 가독성 강화 ──── */
    .stApp, .stApp p, .stApp li, .stApp span, .stApp label {
        color: #e8edf3 !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #ffffff !important;
    }
    /* 채팅 메시지 텍스트 */
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] td,
    [data-testid="stChatMessage"] th,
    [data-testid="stChatMessage"] strong,
    [data-testid="stChatMessage"] em,
    [data-testid="stChatMessage"] blockquote,
    .stMarkdown p, .stMarkdown li, .stMarkdown span,
    .stMarkdown td, .stMarkdown th {
        color: #f0f4f8 !important;
    }
    [data-testid="stChatMessage"] strong {
        color: #ffffff !important;
    }
    /* 사이드바 텍스트 */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li {
        color: #c8d6e5 !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    /* 입력창 컨테이너 배경을 어두운 테마에 맞춤 */
    [data-testid="stChatInput"],
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {
        background-color: #0a0e27 !important;
    }
    /* 입력창 텍스트 필드만 흰색 배경 유지 */
    [data-testid="stChatInput"] textarea {
        color: #1a1a2e !important;
        background-color: #ffffff !important;
        border-radius: 8px !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #6b7280 !important;
    }
    /* blockquote (투자 유의사항 등) */
    blockquote {
        color: #d4dce6 !important;
        border-left-color: #fbbf24 !important;
    }
    
    /* 헤더 영역 */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 50%, #1a4a7a 100%);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        border: 1px solid #3d6a9f;
        box-shadow: 0 4px 20px rgba(30, 58, 95, 0.3);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 28px;
        margin: 0 0 8px 0;
    }
    .main-header p {
        color: #a0c4e8;
        font-size: 14px;
        margin: 0;
    }
    
    /* 파이프라인 상태 표시 */
    .pipeline-box {
        background: rgba(30, 58, 95, 0.3);
        border: 1px solid #3d6a9f;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 13px;
        color: #a0c4e8;
    }
    .pipeline-box .status-ok {
        color: #4ade80;
    }
    .pipeline-box .status-warn {
        color: #fbbf24;
    }
    .pipeline-box .status-block {
        color: #f87171;
    }
    
    /* 시스템 정보 카드 */
    .tech-card {
        background: rgba(45, 90, 135, 0.2);
        border: 1px solid #2d5a87;
        border-radius: 8px;
        padding: 12px;
        margin: 6px 0;
        font-size: 12px;
        color: #8ab4d8;
    }
    .tech-card strong {
        color: #ffffff;
    }
    
    /* 감사 로그 카드 */
    .log-card {
        background: rgba(15, 25, 50, 0.6);
        border: 1px solid #2d3748;
        border-radius: 6px;
        padding: 8px 10px;
        margin: 4px 0;
        font-size: 11px;
        color: #94a3b8;
        font-family: monospace;
    }
    .log-blocked { border-left: 3px solid #f87171; }
    .log-ok { border-left: 3px solid #4ade80; }
    .log-pii { border-left: 3px solid #fbbf24; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 헤더 (제안서 슬라이드 1: 프로젝트 개요)
# ============================================================
st.markdown("""
<div class="main-header">
    <h1>📈 ETF 스마트 어드바이저</h1>
    <p>금융 특화 AI 기반 ETF 투자 상담 서비스 | RAG + 컴플라이언스 파이프라인 적용</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# [개선 2] 임시 파일 정리 함수
# - 세션 종료(프로세스 종료) 시 임시 파일을 자동으로 삭제
# ============================================================
def cleanup_temp_file():
    """세션 종료 시 임시 파일을 삭제합니다."""
    tmp_path = st.session_state.get("tmp_pdf_path")
    if tmp_path and os.path.exists(tmp_path):
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ============================================================
# 사이드바 (설정 & 시스템 정보)
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ 서비스 설정")
    
    # ─── 투자 지식 수준 선택 ───
    st.markdown("### 🎓 투자자 유형 선택")
    user_level = st.radio(
        "투자 지식 수준을 선택해 주세요",
        options=["초급 투자자 (쉬운 설명)", "고급 투자자 (전문가 분석)"],
        index=0,
        help="초급: 금융 용어를 쉽게 풀어 설명합니다\n고급: 전문 용어와 정량적 분석을 포함합니다"
    )
    user_level_key = "beginner" if "초급" in user_level else "advanced"
    
    st.divider()
    
    # ─── PDF 문서 업로드 ───
    st.markdown("### 📄 문서 업로드")
    uploaded_file = st.file_uploader(
        "ETF 관련 PDF 문서를 업로드하세요",
        type=['pdf'],
        help="투자설명서, 공시자료, ETF 가이드 등"
    )
    
    # 기본 데이터 사용 옵션
    use_default_data = st.checkbox(
        "📚 기본 ETF FAQ 데이터 사용",
        value=True,
        help="기본 탑재된 ETF FAQ 지식 베이스를 사용합니다"
    )
    
    st.divider()
    
    # ─── 시스템 아키텍처 정보 ───
    st.markdown("### 🏗️ 시스템 아키텍처")
    
    st.markdown("""
    <div class="tech-card">
        <strong>📊 데이터 파이프라인</strong><br>
        PDF 문서 → 텍스트 추출 → 청크 분할 → 임베딩<br>
        <em>운영 환경: Apache Spark & Hadoop</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="tech-card">
        <strong>🧠 AI 모델 (RAG)</strong><br>
        Vector DB: FAISS (MMR 시맨틱 검색)<br>
        임베딩: Gemini Embedding<br>
        LLM: Gemini 2.5 Flash<br>
        <em>운영 환경: 온프레미스 금융 특화 sLLM</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="tech-card">
        <strong>🛡️ 컴플라이언스</strong><br>
        ✅ 입력 필터 (프롬프트 인젝션 차단)<br>
        ✅ PII 마스킹 (개인정보 보호)<br>
        ✅ 답변 검증 (불완전판매 예방)<br>
        ✅ 투자 유의 고지 자동 삽입<br>
        ✅ 감사 로그 생성
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="tech-card">
        <strong>🚀 인프라</strong><br>
        <em>운영 환경: AWS App Runner (컨테이너 배포)<br>
        API Gateway + CloudWatch 모니터링</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # ─── [개선 3] 감사 로그 UI ───
    st.markdown("### 📋 감사 로그")
    
    compliance_logs = st.session_state.get("compliance_logs", [])
    
    if not compliance_logs:
        st.caption("아직 기록된 로그가 없습니다.")
    else:
        st.caption(f"총 {len(compliance_logs)}건의 로그")
        
        # 최근 5건만 표시
        recent_logs = compliance_logs[-5:][::-1]
        for log in recent_logs:
            is_blocked = not log.get("is_valid", True)
            has_pii = log.get("pii_masked", False)
            card_class = "log-blocked" if is_blocked else ("log-pii" if has_pii else "log-ok")
            status_icon = "🚫" if is_blocked else ("🔒" if has_pii else "✅")
            timestamp = log.get("timestamp", "")[:19].replace("T", " ")
            masked_input = log.get("masked_input", "")[:30]
            
            st.markdown(f"""
            <div class="log-card {card_class}">
                {status_icon} {timestamp}<br>
                <span style="color:#e2e8f0">{masked_input}...</span>
            </div>
            """, unsafe_allow_html=True)
        
        # CSV 다운로드 버튼
        if len(compliance_logs) > 0:
            output = io.StringIO()
            fieldnames = ["timestamp", "user_level", "is_valid", "pii_masked", "masked_input", "response_flagged"]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for log in compliance_logs:
                writer.writerow(log)
            csv_data = output.getvalue()
            
            st.download_button(
                label="📥 감사 로그 CSV 다운로드",
                data=csv_data,
                file_name=f"compliance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )


# ============================================================
# 메인 영역 - RAG 체인 초기화 및 채팅
# ============================================================

def get_pdf_path():
    """
    사용할 PDF 경로를 결정합니다.
    
    [3주차 개선 2] 임시 파일 누수 방지:
    - 업로드 파일을 session_state["tmp_pdf_path"]에 캐싱
    - 같은 파일이면 재사용, 새 파일이면 기존 임시 파일 삭제 후 새로 생성
    """
    if uploaded_file:
        # 업로드 파일의 고유 ID로 변경 여부 판단
        file_id = uploaded_file.file_id if hasattr(uploaded_file, "file_id") else uploaded_file.name
        
        if st.session_state.get("uploaded_file_id") != file_id:
            # 새 파일 업로드 → 기존 임시 파일 삭제
            old_tmp = st.session_state.get("tmp_pdf_path")
            if old_tmp and os.path.exists(old_tmp):
                try:
                    os.unlink(old_tmp)
                except Exception as e:
                    print(f"[WARN] 임시 파일 삭제 실패: {e}")
            
            # 새 임시 파일 생성 (1회만)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                st.session_state["tmp_pdf_path"] = tmp_file.name
                st.session_state["uploaded_file_id"] = file_id
                atexit.register(cleanup_temp_file)  # 프로세스 종료 시 자동 삭제 등록
        
        return st.session_state["tmp_pdf_path"]
    
    if use_default_data:
        default_path = os.path.join(os.path.dirname(__file__), "data", "etf_faq.pdf")
        if os.path.exists(default_path):
            return default_path
    
    return None


# PDF 경로 결정
pdf_path = get_pdf_path()

if pdf_path:
    # ─── [개선 1] 벡터스토어/체인 분리 캐싱 ───
    # 문서(pdf_path)가 바뀐 경우 → 벡터스토어 재생성
    # 레벨(user_level_key)만 바뀐 경우 → 체인만 재생성 (임베딩 비용 절약)
    
    need_vectorstore = (
        "vectorstore" not in st.session_state
        or st.session_state.get("current_pdf_path") != pdf_path
    )
    need_chain = (
        need_vectorstore
        or "rag_chain" not in st.session_state
        or st.session_state.get("current_level") != user_level_key
    )
    
    if need_vectorstore:
        with st.spinner("📄 문서를 분석하고 벡터 인덱스를 생성 중입니다... (최초 1회)"):
            vectorstore = create_vectorstore(pdf_path)
            st.session_state.vectorstore = vectorstore
            st.session_state.current_pdf_path = pdf_path
        st.success("✅ 문서 인덱싱 완료!")
    
    if need_chain:
        level_label = "초급" if user_level_key == "beginner" else "고급"
        with st.spinner(f"🔄 {level_label} 투자자 모드로 AI를 준비 중입니다..."):
            chain, retriever = build_rag_chain(
                st.session_state.vectorstore, user_level_key
            )
            st.session_state.rag_chain = chain
            st.session_state.retriever = retriever
            st.session_state.current_level = user_level_key
        if not need_vectorstore:
            st.success(f"✅ {level_label} 투자자 모드로 전환되었습니다!")
    
    # ─── 컴플라이언스 파이프라인 상태 표시 ───
    level_emoji = "🟢 초급" if user_level_key == "beginner" else "🔵 고급"
    source_label = "업로드 문서" if uploaded_file else "기본 ETF FAQ"
    
    st.markdown(f"""
    <div class="pipeline-box">
        <span class="status-ok">●</span> <strong>파이프라인 활성화</strong> &nbsp;|&nbsp;
        투자자 레벨: {level_emoji} &nbsp;|&nbsp;
        데이터 소스: 📄 {source_label} &nbsp;|&nbsp;
        입력 필터: <span class="status-ok">ON</span> &nbsp;|&nbsp;
        PII 마스킹: <span class="status-ok">ON</span> &nbsp;|&nbsp;
        답변 검증: <span class="status-ok">ON</span>
    </div>
    """, unsafe_allow_html=True)
    
    # ─── 채팅 인터페이스 ───
    if "messages" not in st.session_state:
        st.session_state.messages = []
        welcome_msg = (
            "안녕하세요! 📈 **ETF 스마트 어드바이저**입니다.\n\n"
            "ETF 투자에 대한 궁금한 점을 편하게 물어보세요. "
            "문서 기반의 정확한 정보로 답변 드리겠습니다.\n\n"
            "**질문 예시:**\n"
            "- ETF란 무엇인가요?\n"
            "- ETF 수수료 구조가 궁금합니다\n"
            "- 레버리지 ETF와 인버스 ETF의 차이점은?\n"
            "- ETF 투자 시 세금은 어떻게 되나요?"
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
    
    # 기존 대화 이력 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # ─── 사용자 입력 처리 ───
    if prompt := st.chat_input("ETF에 대해 궁금한 것을 질문해 주세요"):
        original_input = prompt
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            # ──────────────────────────────────────────
            # 컴플라이언스 파이프라인 실행
            # ──────────────────────────────────────────
            
            # [STEP 1] 입력 검증 (예외 발화 탐지 + PII 마스킹)
            input_validation = validate_input(prompt)
            
            if not input_validation["is_valid"]:
                response = input_validation["reason"]
                st.markdown(response)
            else:
                filtered_input = input_validation["filtered_input"]
                
                try:
                    with st.spinner("🔍 문서를 검색하고 답변을 생성 중입니다..."):
                        # [STEP 2] RAG 체인 실행
                        raw_response = st.session_state.rag_chain.invoke(filtered_input)
                        
                        # [STEP 3] 답변 컴플라이언스 검증
                        validation_result = validate_response(raw_response)
                        response = validation_result["final_response"]
                        
                        # [STEP 4] 참고 문서 출처 표시
                        # AI가 "정보를 찾지 못했다"고 답한 경우에는 출처 표시 안 함
                        no_info_keywords = ["확인할 수 없습니다", "찾지 못했습니다", "정보가 없습니다"]
                        has_valid_answer = not any(kw in raw_response for kw in no_info_keywords)
                        
                        if has_valid_answer:
                            try:
                                source_docs = st.session_state.retriever.invoke(filtered_input)
                                if source_docs:
                                    sources = set()
                                    for doc in source_docs:
                                        source_name = os.path.basename(
                                            doc.metadata.get("source", "알 수 없음")
                                        )
                                        # [개선 5] 페이지 번호 0-indexed → +1
                                        page_num = doc.metadata.get("page", 0)
                                        page_display = page_num + 1 if isinstance(page_num, int) else page_num
                                        sources.add(f"`{source_name}` (p.{page_display})")
                                    
                                    source_text = " | ".join(sorted(sources))
                                    response += f"\n\n📄 **참고 문서:** {source_text}"
                            except Exception as src_err:
                                # [개선 4] 출처 표시 실패 시 콘솔에 로그 기록
                                print(f"[WARN] 출처 표시 실패: {src_err}")
                        
                        # [STEP 5] 감사 로그 생성
                        log = create_compliance_log(
                            user_input=original_input,
                            masked_input=filtered_input,
                            response=raw_response,
                            validation_result=validation_result,
                            user_level=user_level_key
                        )
                        
                        if "compliance_logs" not in st.session_state:
                            st.session_state.compliance_logs = []
                        st.session_state.compliance_logs.append(log)
                    
                    st.markdown(response)
                
                except Exception as e:
                    # [개선 4] 실제 에러를 서버 콘솔에 기록 (사용자에게는 안전한 폴백 메시지)
                    print(f"[ERROR] RAG 체인 실행 실패: {type(e).__name__}: {e}")
                    response = get_fallback_response("error")
                    st.markdown(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})

else:
    # PDF 없는 경우 안내
    st.markdown("""
    <div style="
        background: rgba(30, 58, 95, 0.2);
        border: 1px solid #3d6a9f;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        margin-top: 40px;
    ">
        <h2 style="color: #a0c4e8;">📄 문서를 준비해 주세요</h2>
        <p style="color: #6b8db5; font-size: 16px;">
            왼쪽 사이드바에서 ETF 관련 PDF 문서를 업로드하거나,<br>
            "기본 ETF FAQ 데이터 사용" 옵션을 체크하면 바로 시작할 수 있습니다.
        </p>
    </div>
    """, unsafe_allow_html=True)