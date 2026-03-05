"""Media-specific ad specifications and format helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MediaSpec:
    name: str
    headline_limit: int  # 0 = no limit
    description_limit: int  # 0 = no limit
    tone: str
    notes: str = ""


MEDIA_SPECS: dict[str, MediaSpec] = {
    "gfa": MediaSpec(
        name="네이버 GFA",
        headline_limit=25,
        description_limit=45,
        tone="짧고 임팩트 있게",
        notes="네이버 검색/뉴스 지면 노출",
    ),
    "gdn": MediaSpec(
        name="Google GDN",
        headline_limit=30,
        description_limit=90,
        tone="정보 전달형, 명확하게",
        notes="Google 디스플레이 네트워크",
    ),
    "youtube": MediaSpec(
        name="유튜브",
        headline_limit=0,
        description_limit=0,
        tone="영상 연계, 시각적 묘사",
        notes="범퍼/인스트림 광고",
    ),
    "inven": MediaSpec(
        name="인벤 배너",
        headline_limit=20,
        description_limit=30,
        tone="게이머 친화적, 직관적",
        notes="게임 커뮤니티 배너",
    ),
    "instagram": MediaSpec(
        name="인스타그램",
        headline_limit=0,
        description_limit=2200,
        tone="감성적, 트렌디",
        notes="해시태그 30개 포함",
    ),
    "facebook": MediaSpec(
        name="페이스북",
        headline_limit=0,
        description_limit=0,
        tone="정보 전달형, 긴 글 가능",
        notes="링크 공유 + 긴 포스팅",
    ),
    "kakao": MediaSpec(
        name="카카오채널",
        headline_limit=0,
        description_limit=0,
        tone="친근하고 간결하게",
        notes="알림톡 형식",
    ),
    "blog": MediaSpec(
        name="네이버 블로그",
        headline_limit=0,
        description_limit=0,
        tone="SEO 최적화, 정보 제공형",
        notes="소제목+본문 구조, 태그 포함",
    ),
}


def get_media_list() -> list[str]:
    """Return list of media display names."""
    return [spec.name for spec in MEDIA_SPECS.values()]


def get_media_prompt(media_ids: list[str]) -> str:
    """Build a prompt section describing the target media specs."""
    if not media_ids:
        return ""

    parts = ["## 매체별 규격 (반드시 준수)"]
    for mid in media_ids:
        spec = MEDIA_SPECS.get(mid)
        if not spec:
            continue
        line = f"- {spec.name}:"
        if spec.headline_limit:
            line += f" 헤드라인 {spec.headline_limit}자 이내,"
        if spec.description_limit:
            line += f" 설명문 {spec.description_limit}자 이내,"
        line += f" 톤: {spec.tone}"
        if spec.notes:
            line += f" ({spec.notes})"
        parts.append(line)

    return "\n".join(parts)


def get_all_media_prompt() -> str:
    """Build prompt for all media specs."""
    return get_media_prompt(list(MEDIA_SPECS.keys()))
