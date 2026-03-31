from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ReportInputRequest(BaseModel):
    report_text: str | None = None
    report_url: str | None = None
    lesson_id: str | None = None

    @model_validator(mode='after')
    def validate_inputs(self):
        has_text = bool(self.report_text and self.report_text.strip())
        has_url = bool(self.report_url and self.report_url.strip())
        has_lesson = bool(self.lesson_id and self.lesson_id.strip())

        if not (has_text or has_url or has_lesson):
            raise ValueError('Provide at least one of report_text, report_url, or lesson_id')

        if self.report_text:
            self.report_text = self.report_text.strip()
        if self.report_url:
            self.report_url = self.report_url.strip()
        if self.lesson_id:
            self.lesson_id = self.lesson_id.strip()
        return self


class SummaryRequest(ReportInputRequest):
    pass


class SummaryResponse(BaseModel):
    overall_summary: str
    key_points: list[str]
    action_items: list[str]


class LessonFeedbackRequest(ReportInputRequest):
    lesson_label: str | None = None

    @model_validator(mode='after')
    def normalize_label(self):
        if self.lesson_label:
            self.lesson_label = self.lesson_label.strip()
        return self


class SessionCriterion(BaseModel):
    score: int = Field(ge=0, le=100)
    comment: str
    evidence: list[str]

    @field_validator('comment', mode='after')
    @classmethod
    def strip_comment(cls, value: str) -> str:
        return value.strip()


class SessionBreakdown(BaseModel):
    participation: SessionCriterion
    pronunciation: SessionCriterion
    vocabulary: SessionCriterion
    grammar: SessionCriterion
    reaction_confidence: SessionCriterion


class PriorityImprovement(BaseModel):
    skill: Literal['pronunciation', 'vocabulary', 'grammar', 'reaction_confidence', 'participation']
    priority: Literal['high', 'medium', 'low']
    current_state: str
    target_next_lesson: str
    coach_tip: str


class NextLessonStep(BaseModel):
    step: str
    duration_minutes: int = Field(ge=0, le=180)


class LessonFeedbackResponse(BaseModel):
    lesson_label: str
    teacher_tone: str
    overall_comment: str
    session_breakdown: SessionBreakdown
    strengths: list[str]
    priority_improvements: list[PriorityImprovement]
    next_lesson_plan: list[NextLessonStep]
    parent_message: str

    @field_validator(
        'lesson_label',
        'teacher_tone',
        'overall_comment',
        'parent_message',
        mode='after',
    )
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator('priority_improvements', mode='after')
    @classmethod
    def validate_priority_count(cls, value: list[PriorityImprovement]) -> list[PriorityImprovement]:
        if len(value) > 3:
            raise ValueError('priority_improvements must have at most 3 items')
        return value
