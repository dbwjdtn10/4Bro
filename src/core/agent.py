"""Agent mode: autonomous multi-step workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from PyQt6.QtCore import QThread, pyqtSignal

from core.engine import AIEngine
from core.logger import log
from core.media_specs import get_all_media_prompt


@dataclass
class AgentStep:
    name: str
    prompt: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class AgentWorkflow:
    workflow_id: str
    display_name: str
    description: str
    steps: list[AgentStep] = field(default_factory=list)


# Pre-defined workflows
AGENT_WORKFLOWS: dict[str, AgentWorkflow] = {}


def _register(wf: AgentWorkflow):
    AGENT_WORKFLOWS[wf.workflow_id] = wf


_register(AgentWorkflow(
    workflow_id="media_transform",
    display_name="매체별 일괄 변형",
    description="하나의 카피를 여러 매체용으로 한번에 변형",
    steps=[
        AgentStep(
            name="원본 카피 확인",
            prompt=(
                "사용자가 제공한 원본 카피를 확인하고 핵심 메시지를 정리하세요.\n\n"
                "사용자 입력:\n$user_input\n\n"
                "다음을 출력하세요:\n"
                "## 원본 카피\n## 핵심 메시지\n## 타겟 톤"
            ),
        ),
        AgentStep(
            name="매체별 변형",
            prompt=(
                "이전 분석을 바탕으로 각 매체별 규격에 맞게 카피를 변형하세요.\n\n"
                "--- 이전 분석 ---\n$prev_results\n---\n\n"
                + get_all_media_prompt() + "\n\n"
                "각 매체별로 헤드라인 + 설명문을 규격에 맞게 작성하세요."
            ),
            depends_on=["원본 카피 확인"],
        ),
        AgentStep(
            name="최종 정리",
            prompt=(
                "매체별 변형 결과를 깔끔하게 정리하세요.\n\n"
                "--- 변형 결과 ---\n$prev_results\n---\n\n"
                "매체별로 표 형식으로 정리하고, 글자수를 표시해주세요."
            ),
            depends_on=["매체별 변형"],
        ),
    ],
))

_register(AgentWorkflow(
    workflow_id="campaign_package",
    display_name="캠페인 패키지",
    description="타겟 분석 -> 전략 -> 카피 -> SNS -> 기획서",
    steps=[
        AgentStep(
            name="타겟 분석",
            prompt=(
                "다음 제품/캠페인의 타겟을 분석하세요.\n\n"
                "사용자 입력:\n$user_input\n\n"
                "## 핵심 타겟 페르소나\n## 타겟 인구통계\n"
                "## 심리/행동 특성\n## 미디어 소비 패턴\n## 구매 동기 및 장벽"
            ),
        ),
        AgentStep(
            name="전략 수립",
            prompt=(
                "타겟 분석을 바탕으로 마케팅 전략을 수립하세요.\n\n"
                "--- 타겟 분석 ---\n$prev_results\n---\n\n"
                "## 캠페인 컨셉\n## 핵심 메시지 전략\n"
                "## 채널 전략\n## 실행 타임라인"
            ),
            depends_on=["타겟 분석"],
        ),
        AgentStep(
            name="광고 카피",
            prompt=(
                "전략에 맞는 광고 카피를 작성하세요.\n\n"
                "--- 전략 ---\n$prev_results\n---\n\n"
                "## 헤드라인 (10개)\n## 서브 헤드라인 (5개)\n"
                "## 바디카피 (3개 버전)\n## CTA 문구 (5개)"
            ),
            depends_on=["전략 수립"],
        ),
        AgentStep(
            name="SNS 콘텐츠",
            prompt=(
                "전략에 맞는 SNS 콘텐츠를 작성하세요.\n\n"
                "--- 전략 ---\n$prev_results\n---\n\n"
                "## 인스타그램 (캡션 + 해시태그 30개)\n"
                "## 페이스북 (포스팅 + 링크 설명)\n"
                "## 카카오채널 (알림톡 문구)"
            ),
            depends_on=["전략 수립"],
        ),
        AgentStep(
            name="캠페인 기획서",
            prompt=(
                "모든 결과를 종합하여 캠페인 기획서를 작성하세요.\n\n"
                "--- 전체 결과 ---\n$prev_results\n---\n\n"
                "# 캠페인 기획서\n## 1. 캠페인 개요\n## 2. 타겟 분석 요약\n"
                "## 3. 전략 방향\n## 4. 크리에이티브 전략\n"
                "## 5. 채널 믹스\n## 6. KPI 및 성과 측정"
            ),
            depends_on=["광고 카피", "SNS 콘텐츠"],
        ),
    ],
))

_register(AgentWorkflow(
    workflow_id="competitor_research",
    display_name="경쟁사 리서치",
    description="웹 검색 -> 정보 수집 -> 비교 분석 -> 차별화 전략",
    steps=[
        AgentStep(
            name="검색 키워드 도출",
            prompt=(
                "다음 요청에서 경쟁사 리서치를 위한 검색 키워드를 도출하세요.\n\n"
                "사용자 입력:\n$user_input\n\n"
                "## 핵심 검색 키워드 (5개)\n"
                "## 검색 방향\n## 조사 포인트"
            ),
        ),
        AgentStep(
            name="정보 분석",
            prompt=(
                "도출된 키워드를 바탕으로 경쟁사 마케팅을 분석하세요.\n\n"
                "--- 이전 분석 ---\n$prev_results\n---\n\n"
                "$search_context\n\n"
                "## 경쟁사별 마케팅 전략\n## 주요 메시지/카피\n"
                "## 사용 채널\n## 강점/약점"
            ),
            depends_on=["검색 키워드 도출"],
        ),
        AgentStep(
            name="차별화 전략",
            prompt=(
                "경쟁사 분석을 바탕으로 차별화 전략을 제안하세요.\n\n"
                "--- 분석 결과 ---\n$prev_results\n---\n\n"
                "## 차별화 포인트\n## 제안 전략 (3~5개)\n"
                "## 실행 우선순위\n## 예상 효과"
            ),
            depends_on=["정보 분석"],
        ),
    ],
))

_register(AgentWorkflow(
    workflow_id="mass_copy",
    display_name="카피 대량 생성",
    description="방향 분석 -> 대량 생성 -> 분류 정리",
    steps=[
        AgentStep(
            name="방향 분석",
            prompt=(
                "다음 요청의 광고 방향을 분석하세요.\n\n"
                "사용자 입력:\n$user_input\n\n"
                "## 제품 USP\n## 추천 톤앤매너\n"
                "## 크리에이티브 컨셉 (3개)\n## 추천 매체"
            ),
        ),
        AgentStep(
            name="대량 생성",
            prompt=(
                "분석된 방향을 바탕으로 카피를 대량 생성하세요.\n\n"
                "--- 방향 ---\n$prev_results\n---\n\n"
                "## 헤드라인 (50개)\n"
                "각 컨셉별로 15~20개씩 작성하세요.\n"
                "다양한 톤과 스타일을 섞어주세요."
            ),
            depends_on=["방향 분석"],
        ),
        AgentStep(
            name="분류 정리",
            prompt=(
                "생성된 카피를 분류하고 정리하세요.\n\n"
                "--- 생성 결과 ---\n$prev_results\n---\n\n"
                "## 컨셉별 분류\n## TOP 10 추천\n"
                "## 매체별 추천 (GFA/GDN/SNS)\n## 톤별 분류 (강렬/감성/유머)"
            ),
            depends_on=["대량 생성"],
        ),
    ],
))

_register(AgentWorkflow(
    workflow_id="report",
    display_name="보고서 자동화",
    description="데이터 분석 -> 성과 요약 -> 인사이트 -> 제안",
    steps=[
        AgentStep(
            name="데이터 분석",
            prompt=(
                "다음 내용을 분석하세요.\n\n"
                "사용자 입력:\n$user_input\n\n"
                "## 핵심 데이터 요약\n## 주요 수치\n## 트렌드 분석"
            ),
        ),
        AgentStep(
            name="성과 요약",
            prompt=(
                "분석 결과를 성과 중심으로 요약하세요.\n\n"
                "--- 분석 ---\n$prev_results\n---\n\n"
                "## 성과 하이라이트\n## 목표 대비 달성률\n## 채널별 성과"
            ),
            depends_on=["데이터 분석"],
        ),
        AgentStep(
            name="인사이트 및 제안",
            prompt=(
                "성과를 바탕으로 인사이트와 다음 액션을 제안하세요.\n\n"
                "--- 성과 ---\n$prev_results\n---\n\n"
                "## 핵심 인사이트 (5개)\n## 개선 포인트\n"
                "## 다음 캠페인 제안\n## 예산 재분배 제안"
            ),
            depends_on=["성과 요약"],
        ),
    ],
))


class AgentWorker(QThread):
    """Executes agent workflow steps sequentially with streaming."""

    step_started = pyqtSignal(int, str)         # (step_index, step_name)
    token_received = pyqtSignal(int, str)       # (step_index, token)
    step_completed = pyqtSignal(int, str, str)  # (step_index, step_name, full_text)
    workflow_finished = pyqtSignal(str)          # combined results text
    workflow_error = pyqtSignal(str)

    def __init__(
        self,
        engine: AIEngine,
        workflow: AgentWorkflow,
        user_input: str,
        system_prompt: str = "",
        search_context: str = "",
        search_query: str = "",
    ):
        super().__init__()
        self._engine = engine
        self._workflow = workflow
        self._user_input = user_input
        self._system_prompt = system_prompt
        self._search_context = search_context
        self._search_query = search_query
        self._cancelled = False
        self._results: dict[str, str] = {}

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._execute()
        except Exception as e:
            if not self._cancelled:
                self.workflow_error.emit(str(e))

    def _execute(self):
        # Run web search in this worker thread (non-blocking for UI)
        if self._search_query and not self._search_context:
            try:
                from core.web_search import search_web, format_search_results
                results = search_web(self._search_query, max_results=5)
                self._search_context = f"[웹 검색 결과]\n{format_search_results(results)}"
            except Exception as e:
                log.warning(f"에이전트 웹 검색 실패: {e}")
                self._search_context = "(웹 검색 실패)"

        all_results = []

        for i, step in enumerate(self._workflow.steps):
            if self._cancelled:
                return

            self.step_started.emit(i, step.name)

            # Build prompt with context
            prev_results = "\n\n".join(
                f"### {name}\n{text}" for name, text in self._results.items()
            )
            prompt = Template(step.prompt).safe_substitute(
                user_input=self._user_input,
                prev_results=prev_results,
                search_context=self._search_context,
            )

            messages = [{"role": "user", "content": prompt}]
            full_response = ""

            for chunk in self._engine.stream_chat(messages, self._system_prompt):
                if self._cancelled:
                    return
                full_response += chunk
                self.token_received.emit(i, chunk)

            self._results[step.name] = full_response
            self.step_completed.emit(i, step.name, full_response)
            all_results.append(f"## {step.name}\n{full_response}")

        combined = "\n\n---\n\n".join(all_results)
        self.workflow_finished.emit(combined)

    def get_results(self) -> dict[str, str]:
        return dict(self._results)
