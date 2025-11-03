from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid

class CreateInterviewRequest(BaseModel):
    name: str
    objective: str
    mode: str = "predefined"  # "predefined" or "dynamic"
    question_count: Optional[int] = 5
    auto_question_generate: bool = True
    manual_questions: Optional[List[Dict[str, Any]]] = None

class UploadCVRequest(BaseModel):
    candidate_name: str
    candidate_email: str

class GenerateQuestionsRequest(BaseModel):
    question_count: int = 5

class StartInterviewRequest(BaseModel):
    candidate_name: str
    candidate_email: str

class SubmitAnswerRequest(BaseModel):
    question: str
    transcript: str

class EndInterviewRequest(BaseModel):
    reason: Optional[str] = "Candidate requested to end interview"

class EndInterviewResponse(BaseModel):
    interview_completed: bool
    total_questions: int
    answered_questions: int
    final_analysis: Optional[Dict[str, Any]] = None
    overall_score: Optional[int] = None
    recommendations: Optional[List[str]] = None
    message: str

class ContextSummaryResponse(BaseModel):
    context_id: str
    summary: Dict[str, Any]

class InterviewResponse(BaseModel):
    id: str
    name: str
    objective: str
    mode: str
    question_count: int
    context: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None
    candidate_link: Optional[str] = None

class DynamicQuestion(BaseModel):
    id: str
    question: str
    type: str
    difficulty: str
    expected_answer: str

class ResponseAnalysis(BaseModel):
    relevance_score: int
    completeness_score: int
    clarity_score: int
    overall_score: int
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    follow_up_questions: List[str]