from pydantic import BaseModel
from typing import List, Optional

class SolutionResponse(BaseModel):
    summarized_solution: Optional[str]
    is_correct: Optional[bool]
    feedback: str
    performance_explanation: Optional[str]
    performance: Optional[int]

class QuestionGeneration(BaseModel):
    possible_topics: List[str]
    topic: str
    possible_questions: List[str]
    question: str
    solving_process: str
    expected_answer: str

