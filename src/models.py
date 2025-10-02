from pydantic import BaseModel


class SolutionResponse(BaseModel):
    summarized_solution: str | None
    is_correct: bool | None
    feedback: str
    performance_explanation: str | None
    performance: int | None


class QuestionGeneration(BaseModel):
    possible_topics: list[str]
    topic: str
    possible_questions: list[str]
    question: str
    solving_process: str
    expected_answer: str
