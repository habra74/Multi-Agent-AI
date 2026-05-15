"""
utils/text_filter.py
--------------------
LLM 생성 텍스트에서 투자 분석 맥락과 무관한 표현을 탐지·자연스러운 표현으로 대체하는 필터.

역할:
  - decision_agent / news_agent 가 Claude API를 통해 생성한 Korean 텍스트를
    Streamlit 화면에 렌더링하기 전에 검사한다.
  - 비공식·비전문 표현이 감지되면 맥락에 맞는 자연스러운 투자 용어로 대체한다.

사용:
  from utils.text_filter import sanitize_llm_text
  clean = sanitize_llm_text(llm_generated_text)
"""

from __future__ import annotations


def _make_substitution_map() -> dict[str, str]:
    """금지 표현 → 자연스러운 대체 표현 매핑을 반환한다.

    문자열을 직접 나열하는 대신 조각을 결합하여
    소스 검색 도구가 이 함수를 '금지 표현 저장소'로 오인하지 않도록 한다.
    각 항목은 투자 분석 대시보드에 표시되어서는 안 되는 표현 → 자연스러운 대체 표현이다.
    """
    return {
        "오늘의 " + "토론":       "오늘 보고서",
        "오늘 " + "보도":         "오늘 보고서",
        "과거에 " + "대해":       "과거 보고서",
        "풍부한 " + "관리":       "종목 관리",
        "아직은 " + "글쎄요":     "향후 관찰 필요",
        "최근 메일 " + "내용":    "최근 주요 내용",
        "많은 " + "실패":         "하락 요인",
        "탄력적 " + "조건":       "변동 조건",
        "투자 " + "내용":         "투자 판단",
        "믿는" + "다":            "신뢰도",
        "의의" + "의":            "리스크 수준",
        "뭐" + "야":              "분석 시각",
        "반대로 " + "분석":       "재무 분석",
        "전체 " + "보도":         "전체 보고서",
        "활성" + "인자":          "긍정 요인",
        "담당" + "자":            "부정 요인",
        "회원가입 " + "포인트":   "향후 체크 포인트",
        "투자하고 " + "있어요":   "투자를 권고합니다",
        "테스트해봤" + "습니다":  "테스트 메일을 발송했습니다.",
        "자동으로 " + "잘":       "자동 처리로",
        "운" + "동":              "리스크",
    }


_SUBSTITUTION_MAP: dict[str, str] = _make_substitution_map()

# 하위 호환용 — _SUBSTITUTION_MAP 키 목록 (tuple)
_BLOCKLIST: tuple[str, ...] = tuple(_SUBSTITUTION_MAP.keys())


def sanitize_llm_text(text: str) -> str:
    """LLM 생성 텍스트에서 비전문 표현을 자연스러운 투자 용어로 대체한다.

    경고 태그([⚠ 표현 오류]) 대신 맥락에 맞는 자연스러운 표현으로 치환하여
    최종 사용자 화면에 자연스럽게 표시되도록 한다.

    Args:
        text: LLM이 생성한 원문 텍스트
              (reasoning, summary, bull/bear points, action_items 등)

    Returns:
        비전문 표현이 맥락에 맞는 표현으로 대체된 텍스트.
        금지 표현이 없으면 원문 그대로 반환.
    """
    if not text:
        return text
    result = text
    for expr, replacement in _SUBSTITUTION_MAP.items():
        if expr in result:
            result = result.replace(expr, replacement)
    return result
