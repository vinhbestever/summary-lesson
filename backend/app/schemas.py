from pydantic import BaseModel, field_validator


class SummaryRequest(BaseModel):
    report_text: str
    lesson_id: str | None = None

    @field_validator('report_text')
    @classmethod
    def validate_report_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError('report_text must not be blank')
        return value.strip()


class SummaryResponse(BaseModel):
    overall_summary: str
    key_points: list[str]
    action_items: list[str]
