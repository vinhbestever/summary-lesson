from pydantic import BaseModel, model_validator


class SummaryRequest(BaseModel):
    report_text: str | None = None
    report_url: str | None = None
    lesson_id: str | None = None

    @model_validator(mode='after')
    def validate_inputs(self) -> 'SummaryRequest':
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


class SummaryResponse(BaseModel):
    overall_summary: str
    key_points: list[str]
    action_items: list[str]
