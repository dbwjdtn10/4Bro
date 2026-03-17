"""System prompts and message-building utilities for 4Bro v3.2.

Provides chat mode system prompts (ad expert / general), text cleaning,
token-budget management (truncation + history trimming), and message assembly.
"""

import re

# ===========================================================================
# Chat mode system prompts
# ===========================================================================

SYSTEM_AD_EXPERT = (
    "당신은 '4Bro'라는 AI 광고 마케팅 어시스턴트입니다.\n\n"
    "## 역할\n"
    "- 대한민국 최고의 광고 카피라이터이자 마케팅 전략가\n"
    "- 사용자(광고 마케터)의 업무를 도와주는 전문 파트너\n\n"
    "## 전문 분야\n"
    "- 광고 카피 작성 (헤드라인, 바디카피, CTA, 슬로건)\n"
    "- 매체별 광고 규격에 맞춘 변형 (GFA, GDN, 유튜브, 인벤, SNS)\n"
    "- 캠페인 전략 수립 및 기획서 작성\n"
    "- 타겟 분석 및 페르소나 설계\n"
    "- SNS 콘텐츠 기획 (인스타그램, 페이스북, 블로그)\n"
    "- A/B 카피 비교 분석\n"
    "- 경쟁사 분석 및 차별화 전략\n\n"
    "## 매체별 광고 규격\n"
    "- 네이버 GFA: 헤드라인 25자, 설명문 45자\n"
    "- Google GDN: 헤드라인 30자, 설명문 90자\n"
    "- 유튜브: 제한 없음 (영상 연계)\n"
    "- 인벤 배너: 헤드라인 20자, 설명문 30자\n"
    "- 인스타그램: 캡션 2,200자, 해시태그 30개\n"
    "- 페이스북: 제한 없음 (정보 전달형)\n\n"
    "## 응답 원칙\n"
    "- 반드시 한국어로 응답\n"
    "- 구체적이고 바로 사용 가능한 결과물 제공\n"
    "- 여러 방향/버전을 제안하여 선택지 제공\n"
    "- 매체 규격을 정확히 지키기\n"
    "- 마크다운 형식으로 깔끔하게 정리\n"
    "- 친근하지만 전문적인 톤 유지\n"
)

SYSTEM_GENERAL = (
    "당신은 '4Bro'라는 AI 어시스턴트입니다.\n\n"
    "## 역할\n"
    "- 사용자의 다양한 업무를 도와주는 범용 어시스턴트\n"
    "- 이메일 작성, 보고서 작성, 번역, 요약, 질의응답 등\n\n"
    "## 응답 원칙\n"
    "- 반드시 한국어로 응답\n"
    "- 명확하고 구조화된 답변 제공\n"
    "- 마크다운 형식으로 깔끔하게 정리\n"
    "- 친근하지만 전문적인 톤 유지\n"
)

# Mode map
SYSTEM_PROMPTS = {
    "ad_expert": SYSTEM_AD_EXPERT,
    "general": SYSTEM_GENERAL,
}


def get_system_prompt(mode: str = "ad_expert") -> str:
    """Get system prompt for the given mode."""
    return SYSTEM_PROMPTS.get(mode, SYSTEM_AD_EXPERT)


# Approximate char limits (1 token ≈ 3~4 chars for Korean)
# Gemini 2.5 Flash has 1M token context (~3M Korean chars) — be generous
MAX_USER_INPUT_CHARS = 500_000     # ~125k tokens — large inputs welcome
MAX_DOC_CHARS = 500_000            # ~125k tokens — large documents welcome
MAX_HISTORY_CHARS = 200_000        # ~50k tokens — keep generous history
TRUNCATION_NOTICE = "\n\n⚠️ [텍스트가 너무 길어 일부만 포함되었습니다]"


_CLEAN_THRESHOLD = 3000  # Only clean text longer than this (likely web-copied)


def _clean_text(text: str) -> str:
    """Clean and compress text to reduce token waste.

    Only applies to long text (>3000 chars) that is likely web-copied.
    Short normal messages are returned as-is.
    """
    if len(text) < _CLEAN_THRESHOLD:
        return text

    # Strip HTML tags (from web copy-paste)
    text = re.sub(r'<[^>]+>', ' ', text)

    # Remove common web footer/boilerplate lines (only full-line matches)
    text = re.sub(
        r'^.{0,10}(Copyright|©|All [Rr]ights [Rr]eserved'
        r'|개인정보\s*처리방침|이용약관|사업자\s*등록번호'
        r'|통신판매업\s*신고).+$',
        '', text, flags=re.MULTILINE
    )

    # Collapse multiple whitespace/newlines
    text = re.sub(r'[ \t]+', ' ', text)          # multiple spaces → single
    text = re.sub(r'\n{3,}', '\n\n', text)       # 3+ newlines → 2
    text = re.sub(r'(\n\s*){3,}', '\n\n', text)  # blank line spam

    # Remove duplicate consecutive lines
    lines = text.split('\n')
    deduped = []
    prev = None
    for line in lines:
        stripped = line.strip()
        if stripped != prev:
            deduped.append(line)
            prev = stripped
    text = '\n'.join(deduped)

    return text.strip()


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    """Truncate text to limit chars. Returns (text, was_truncated)."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + TRUNCATION_NOTICE, True


def _trim_history(history: list[dict], char_limit: int) -> list[dict]:
    """Keep recent history within char_limit, dropping oldest pairs first.

    Removes messages in user/assistant pairs to keep role alternation valid.
    """
    total = sum(len(m["content"]) for m in history)
    if total <= char_limit:
        return list(history)

    trimmed = list(history)
    while len(trimmed) >= 2 and total > char_limit:
        # Remove oldest pair (user + assistant)
        removed1 = trimmed.pop(0)
        total -= len(removed1["content"])
        if trimmed and trimmed[0]["role"] != removed1["role"]:
            removed2 = trimmed.pop(0)
            total -= len(removed2["content"])

    return trimmed


def build_chat_messages(
    history: list[dict],
    user_input: str,
    doc_text: str = "",
) -> list[dict]:
    """Build message list for chat API call.

    history: [{"role": "user"|"assistant", "content": str}, ...]
    Returns messages WITHOUT system prompt (system prompt handled separately by engine).
    Cleans text, truncates long inputs, and trims old history to prevent token overflow.
    """
    # Clean text first (removes noise, compresses whitespace)
    user_input = _clean_text(user_input)
    if doc_text:
        doc_text = _clean_text(doc_text)

    # Truncate if still too long after cleaning
    user_input, _ = _truncate(user_input, MAX_USER_INPUT_CHARS)
    if doc_text:
        doc_text, _ = _truncate(doc_text, MAX_DOC_CHARS)

    # Trim history to fit token budget
    messages = _trim_history(history, MAX_HISTORY_CHARS)

    # Build final user message
    if doc_text:
        user_content = (
            f"[첨부 문서 내용]\n{doc_text}\n\n"
            f"---\n\n{user_input}"
        )
    else:
        user_content = user_input

    messages.append({"role": "user", "content": user_content})
    return messages
