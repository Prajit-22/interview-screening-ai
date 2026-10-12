from pydantic import BaseModel, Field, field_validator


class AnswerRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    answer: str = Field(min_length=1, max_length=10000)

    @field_validator('answer')
    @classmethod
    def meaningful_answer(cls, value):
        if not value.strip():
            raise ValueError('Answer cannot be blank')
        return value.strip()
