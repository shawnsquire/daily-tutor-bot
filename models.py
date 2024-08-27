from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional

class User:
    def __init__(self, user_id: str, subject: str, next_problem: str = None, status: str = None):
        self.user_id = user_id
        self.subject = subject
        self.next_problem = next_problem
        self.status = status

    def update_status(self, status: str):
        self.status = status

    def update_next_problem(self, next_problem: str):
        self.next_problem = next_problem


class Session:
    def __init__(self, user_id: str, subject: str, topic: str = None):
        self.user_id = user_id
        self.subject = subject
        self.topic = topic
        self.start_time = datetime.now().isoformat()
        self.end_time = None
        self.performance_summary = None

    def end(self, performance_summary: str = None):
        self.end_time = datetime.now().isoformat()
        self.performance_summary = performance_summary

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

