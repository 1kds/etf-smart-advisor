"""
컴플라이언스 모듈 (compliance.py)
=================================
제안서 슬라이드 4 "리스크 통제 및 컴플라이언스"를 코드로 구현

기능:
1. 예외 발화 탐지 (입력 필터) - 비금융 질문, 프롬프트 인젝션 차단
2. PII 마스킹 - 주민등록번호, 계좌번호, 전화번호 등 개인식별정보 마스킹
3. 답변 컴플라이언스 검증 (출력 필터) - 단정적 투자 권유 표현 감지
4. 투자 유의 고지문 자동 삽입
"""

import re
from datetime import datetime


# ============================================================
# [1] 예외 발화 탐지 분류기 (입력 필터)
# - 제안서: "질문 범위를 벗어난 비금융 관련 질문이나
#   악의적 프롬프트 주입(Prompt Injection) 시도를 입구 단계에서 사전 차단"
# ============================================================

# 프롬프트 인젝션 패턴 (악의적 시도 탐지)
PROMPT_INJECTION_PATTERNS = [
    r"(?i)(ignore|무시).*(instruction|지시|명령|위의|이전)",
    r"(?i)(pretend|가장|역할).*(you are|너는|당신은)",
    r"(?i)(system\s*prompt|시스템\s*프롬프트)",
    r"(?i)(jailbreak|탈옥)",
    r"(?i)(reveal|공개|알려).*(prompt|프롬프트|지시)",
    r"(?i)DAN\s*mode",
]

# 비금융 주제 키워드 (금융과 무관한 질문 필터링)
NON_FINANCIAL_KEYWORDS = [
    "날씨", "요리", "레시피", "게임", "영화 추천", "연애",
    "정치", "종교", "욕설", "운세", "점성술", "다이어트",
]

# 금융 관련 키워드 (화이트리스트)
FINANCIAL_KEYWORDS = [
    "ETF", "주식", "펀드", "투자", "수익률", "배당", "지수",
    "코스피", "코스닥", "나스닥", "S&P", "채권", "금리",
    "환율", "자산", "포트폴리오", "리밸런싱", "분산투자",
    "매수", "매도", "수수료", "보수", "NAV", "순자산",
    "상장", "추적오차", "벤치마크", "레버리지", "인버스",
    "섹터", "테마", "원자재", "금", "은", "원유",
    "ISA", "IRP", "연금", "세금", "양도소득세",
    "증권", "거래소", "호가", "시가총액", "거래량",
    "공시", "보고서", "운용", "상품", "가입",
    "계좌", "HTS", "MTS", "챗봇", "상담",
]


def check_prompt_injection(user_input: str) -> dict:
    """
    프롬프트 인젝션 시도를 탐지합니다.
    
    Returns:
        {"is_safe": bool, "reason": str}
    """
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, user_input):
            return {
                "is_safe": False,
                "reason": "🚫 보안 정책에 의해 차단된 요청입니다. 금융 관련 질문을 입력해 주세요."
            }
    return {"is_safe": True, "reason": ""}


def check_financial_relevance(user_input: str) -> dict:
    """
    입력이 금융/ETF 관련 질문인지 판별합니다.
    
    - 금융 키워드가 하나라도 포함되면 → 통과
    - 금융 키워드 없이 비금융 키워드가 있으면 → 차단
    - 둘 다 없으면 → 통과 (모호한 질문은 허용)
    
    Returns:
        {"is_relevant": bool, "reason": str}
    """
    input_lower = user_input.lower()
    
    # 금융 키워드 포함 여부
    has_financial = any(kw.lower() in input_lower for kw in FINANCIAL_KEYWORDS)
    if has_financial:
        return {"is_relevant": True, "reason": ""}
    
    # 비금융 키워드 포함 여부
    has_non_financial = any(kw in user_input for kw in NON_FINANCIAL_KEYWORDS)
    if has_non_financial:
        return {
            "is_relevant": False,
            "reason": "💡 저는 ETF 및 금융 투자 전문 AI 어드바이저입니다. "
                       "금융·투자 관련 질문을 입력해 주시면 정확한 답변을 드리겠습니다.\n\n"
                       "**질문 예시:**\n"
                       "- ETF란 무엇인가요?\n"
                       "- ETF 수수료 구조가 궁금합니다\n"
                       "- S&P 500 ETF와 코스피 200 ETF 차이점은?"
        }
    
    # [3주차 개선 7] 둘 다 없는 경우: 인사말 예외 처리
    # - 명백한 인사말(안녕, 고마워, 하이 등)은 허용 (챗봇 게 수준의 자연스러운 수신)
    # - 그 외 잡담성 질문은 차단
    GREETING_KEYWORDS = ["안녕", "하이", "헬로", "반가워", "고마워", "감사", "실례합니다", "hi", "hello", "thanks"]
    has_greeting = any(kw in user_input for kw in GREETING_KEYWORDS)
    if has_greeting:
        return {"is_relevant": True, "reason": ""}  # 인사말은 허용
    
    # 잡담성 질문 차단 (여전히 모든 키워드 없는 경우)
    # 질문이 너무 짧으면 (오타 등) 데 허용
    if len(user_input.strip()) <= 2:
        return {"is_relevant": True, "reason": ""}
    
    return {
        "is_relevant": False,
        "reason": "💡 저는 ETF 및 금융 투자 전문 AI 어드바이저입니다. \n"
                   "ETF 및 금융 투자 관련 질문을 입력해 주시면 정확한 답변을 드리겠습니다.\n\n"
                   "**질문 예시:**\n"
                   "- ETF란 무엇인가요?\n"
                   "- ETF 수수료 구조가 궁금합니다\n"
                   "- S&P 500 ETF와 코스피 200 ETF 차이점은?"
    }


def validate_input(user_input: str) -> dict:
    """
    입력 검증 파이프라인 (통합)
    제안서: "입구 단계에서 사전 차단"
    
    Returns:
        {"is_valid": bool, "filtered_input": str, "reason": str}
    """
    # 빈 입력 체크
    if not user_input or not user_input.strip():
        return {
            "is_valid": False,
            "filtered_input": "",
            "reason": "질문을 입력해 주세요."
        }
    
    # 1단계: 프롬프트 인젝션 체크
    injection_check = check_prompt_injection(user_input)
    if not injection_check["is_safe"]:
        return {
            "is_valid": False,
            "filtered_input": "",
            "reason": injection_check["reason"]
        }
    
    # 2단계: 금융 관련성 체크
    relevance_check = check_financial_relevance(user_input)
    if not relevance_check["is_relevant"]:
        return {
            "is_valid": False,
            "filtered_input": "",
            "reason": relevance_check["reason"]
        }
    
    # 3단계: PII 마스킹 (통과된 입력에 대해)
    masked_input = mask_pii(user_input)
    
    return {
        "is_valid": True,
        "filtered_input": masked_input,
        "reason": ""
    }


# ============================================================
# [2] PII 마스킹 (민감정보 보호)
# - 제안서: "개인식별정보(PII) 누출 차단"
# ============================================================

PII_PATTERNS = {
    "주민등록번호": r"\d{6}[-\s]?\d{7}",
    "계좌번호": r"\d{3,4}[-\s]?\d{2,4}[-\s]?\d{4,6}",
    "전화번호": r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}",
    "이메일": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "카드번호": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
}


def mask_pii(text: str) -> str:
    """
    텍스트에서 개인식별정보(PII)를 마스킹 처리합니다.
    제안서: "민감정보 및 규제준수 마스킹"
    """
    masked = text
    for pii_type, pattern in PII_PATTERNS.items():
        masked = re.sub(pattern, f"[{pii_type} 마스킹됨]", masked)
    return masked


# ============================================================
# [3] 답변 컴플라이언스 검증 (출력 필터)
# - 제안서: "0.1초 신속 사전 검증 필터"
#   → 사용자 화면에 답변이 송출되기 전 검증
# - 제안서: "불완전판매 예방 키워드 자동 필터링"
# ============================================================

# 단정적 투자 권유 표현 (불완전판매 위험)
RISKY_EXPRESSIONS = [
    r"반드시\s*(오를|상승|수익)",
    r"확실(히|한)\s*(수익|이익|오)",
    r"무조건\s*(사|매수|투자|오)",
    r"원금\s*(보장|보전)",
    r"손실\s*(없|안\s*나|불가능)",
    r"100%\s*(수익|이익|안전)",
    r"절대(로)?\s*(안전|손실.*없)",
]

# 투자 유의 고지문
INVESTMENT_DISCLAIMER = (
    "\n\n---\n"
    "⚠️ **투자 유의사항**\n\n"
    "> 본 답변은 AI가 문서를 기반으로 생성한 참고 정보이며, "
    "투자 판단의 최종 책임은 투자자 본인에게 있습니다. "
    "ETF를 포함한 모든 금융 상품은 원금 손실의 위험이 있으며, "
    "과거 수익률이 미래 수익을 보장하지 않습니다. "
    "투자 전 반드시 투자설명서를 확인하시기 바랍니다."
)


def validate_response(response: str) -> dict:
    """
    AI 응답에 대한 컴플라이언스 검증을 수행합니다.
    제안서: "답변 생성 전 100ms 이내의 고성능 정규식 및 분류 필터"
    
    Returns:
        {"is_compliant": bool, "warnings": list, "final_response": str}
    """
    warnings = []
    
    # 단정적 투자 권유 표현 감지
    for pattern in RISKY_EXPRESSIONS:
        match = re.search(pattern, response)
        if match:
            warnings.append(
                f"⚠️ 단정적 투자 권유 표현 감지: '{match.group()}'"
            )
    
    # PII 마스킹 (답변에도 적용)
    masked_response = mask_pii(response)
    
    # 투자 유의 고지문 추가
    final_response = masked_response + INVESTMENT_DISCLAIMER
    
    # 경고가 있으면 답변 상단에 경고 삽입
    if warnings:
        warning_text = "\n".join(warnings)
        final_response = (
            f"⚠️ **컴플라이언스 알림**\n{warning_text}\n\n"
            f"아래 답변에는 AI가 생성한 표현이 포함되어 있으며, "
            f"투자를 권유하거나 수익을 보장하는 것이 아닙니다.\n\n---\n\n"
            f"{final_response}"
        )
    
    return {
        "is_compliant": len(warnings) == 0,
        "warnings": warnings,
        "final_response": final_response
    }


# ============================================================
# [4] 룰베이스 폴백 (Fallback)
# - 제안서: "AI가 확실한 출처 데이터를 찾지 못하는 경우,
#   허위 사실을 꾸며내지 않고 사전에 지정된 안전 멘트로 응답"
# ============================================================

FALLBACK_RESPONSES = {
    "no_context": (
        "죄송합니다. 현재 보유한 문서에서 해당 질문에 대한 "
        "신뢰할 수 있는 정보를 찾지 못했습니다.\n\n"
        "**다음 방법을 시도해 보세요:**\n"
        "1. 질문을 좀 더 구체적으로 바꿔서 입력해 주세요\n"
        "2. 관련 ETF 상품명이나 키워드를 포함해 주세요\n"
        "3. 추가 PDF 문서를 업로드해 주세요\n\n"
        "또는 증권사 고객센터(1588-XXXX)로 직접 문의하시면 "
        "전문 상담원이 도움을 드리겠습니다."
    ),
    "error": (
        "일시적인 시스템 오류가 발생했습니다. "
        "잠시 후 다시 시도해 주세요.\n\n"
        "문제가 지속되면 고객센터로 문의 바랍니다."
    ),
}


def get_fallback_response(fallback_type: str = "no_context") -> str:
    """
    폴백 응답을 반환합니다.
    """
    response = FALLBACK_RESPONSES.get(fallback_type, FALLBACK_RESPONSES["error"])
    return response + INVESTMENT_DISCLAIMER


# ============================================================
# [5] 컴플라이언스 로그 (감사 체계)
# - 제안서: "모든 답변 생성 히스토리와 검증 필터를 거친 로그를 보관"
# ============================================================

def create_compliance_log(user_input: str, masked_input: str, 
                          response: str, validation_result: dict,
                          user_level: str) -> dict:
    """
    컴플라이언스 감사 로그를 생성합니다.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "user_level": user_level,
        "input_original_length": len(user_input),
        "input_was_masked": user_input != masked_input,
        "response_length": len(response),
        "compliance_passed": validation_result["is_compliant"],
        "warnings_count": len(validation_result["warnings"]),
        "warnings": validation_result["warnings"],
    }
