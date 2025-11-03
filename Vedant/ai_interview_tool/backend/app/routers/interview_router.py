from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import base64
import docx
import uuid
import json
import os
import tempfile
import io
from pathlib import Path
import time
from datetime import datetime, timezone
import PyPDF2
from db import AsyncSessionLocal
from models import Interview, Response
from schemas.interview_schema import (
    CreateInterviewRequest, 
    UploadCVRequest,
    GenerateQuestionsRequest,
    StartInterviewRequest,
    SubmitAnswerRequest,
    EndInterviewRequest,
    EndInterviewResponse,
    ContextSummaryResponse,
    InterviewResponse
)
from services.summarization_service import summarization_service
from services.llm_service import llm_service
from services.tts_service import tts_service
from utils.redis_utils import create_session, set_session_meta
import secrets

router = APIRouter(prefix="/api/interview", tags=["interview"])

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    try:
        file_extension = Path(filename).suffix.lower()
        
        if file_extension == '.txt':
            return file_content.decode('utf-8', errors='ignore')
        
        elif file_extension == '.pdf':
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except ImportError:
                return "PDF processing requires PyPDF2. Please install: pip install PyPDF2"
        
        elif file_extension in ['.docx', '.doc']:
            try:
                doc = docx.Document(io.BytesIO(file_content))
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
            except ImportError:
                return "DOCX processing requires python-docx. Please install: pip install python-docx"
        
        else:
            return file_content.decode('utf-8', errors='ignore')
            
    except Exception as e:
        return f"Error extracting text from file: {str(e)}"

@router.post("/create-interview", response_model=InterviewResponse)
async def create_interview(
    request: CreateInterviewRequest = None,
    jd_file: UploadFile = File(None)
):
    try:
        async with AsyncSessionLocal() as db:
            if request is None:
                class Dummy: pass
                request = Dummy()
                request.name = "Untitled Interview"
                request.objective = ""
                request.mode = "predefined"
                request.question_count = 5
                request.auto_question_generate = True
                request.manual_questions = []

            interview = Interview(
                name=request.name,
                objective=request.objective,
                question_mode=request.mode,
                question_count=request.question_count,
                auto_question_generate=request.auto_question_generate,
                manual_questions=request.manual_questions or []
            )
            
            db.add(interview)
            await db.commit()
            await db.refresh(interview)
            
            if jd_file is not None:
                allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
                file_extension = Path(jd_file.filename).suffix.lower()
                if file_extension not in allowed_extensions:
                    raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")
                jd_bytes = await jd_file.read()
                jd_text = extract_text_from_file(jd_bytes, jd_file.filename)
                context_data = await summarization_service.summarize_jd(jd_text)
                interview.context = context_data
                await db.commit()

            candidate_link = f"/candidate/interview/{interview.id}"

            return InterviewResponse(
                id=str(interview.id),
                name=interview.name,
                objective=interview.objective,
                mode=interview.question_mode,
                question_count=interview.question_count,
                context=interview.context,
                questions=interview.llm_generated_questions,
                candidate_link=candidate_link
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{interview_id}/responses")
async def list_responses(interview_id: str):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Interview).where(Interview.id == interview_id))
            interview = result.scalar_one_or_none()
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")

            result = await db.execute(select(Response).where(Response.interview_id == interview_id))
            rows = result.scalars().all() or []
            payload = []
            for r in rows:
                answered = len(r.qa_history or [])
                payload.append({
                    "response_id": str(r.id),
                    "name": r.name,
                    "email": r.email,
                    "answered_questions": answered
                })
            return {"ok": True, "responses": payload}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_interviews():
    try:    
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Interview))
            interviews = result.scalars().all() or []
            items = []
            for it in interviews:
                res = await db.execute(select(Response).where(Response.interview_id == it.id))
                responses = res.scalars().all() or []
                items.append({
                    "id": str(it.id),
                    "name": it.name,
                    "mode": it.question_mode,
                    "question_count": it.question_count,
                    "responses_count": len(responses),
                })
            return {"ok": True, "interviews": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/response/{response_id}")
async def get_response_detail(response_id: str):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Response).where(Response.id == response_id))
            response = result.scalar_one_or_none()
            if not response:
                raise HTTPException(status_code=404, detail="Response not found")

            result = await db.execute(select(Interview).where(Interview.id == response.interview_id))
            interview = result.scalar_one_or_none()
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")

            qa_history = response.qa_history or []
            final_analysis = None
            overall_score = None
            if qa_history and interview.context:
                try:
                    final_analysis = await llm_service.generate_final_analysis(
                        str(interview.id), qa_history
                    )
                    overall_score = final_analysis.get("overall_score")
                except Exception as e:
                    print(f"[WARN] final_analysis failed: {e}")

            return {
                "ok": True,
                "response_id": str(response.id),
                "interview_id": str(interview.id),
                "name": response.name,
                "email": response.email,
                "qa_history": qa_history,
                "final_analysis": final_analysis,
                "overall_score": overall_score,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{interview_id}/questions/generate")
async def generate_questions(
    interview_id: str,
    request: GenerateQuestionsRequest
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Interview).where(Interview.id == interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            context_for_llm = summarization_service.get_context_for_llm(interview.context)

            target_count = request.question_count or interview.question_count or 5
            
            if interview.question_mode == "predefined" and (interview.auto_question_generate is False) and interview.manual_questions:
                manual_list = interview.manual_questions if isinstance(interview.manual_questions, list) else []
                questions = manual_list[:target_count]
                interview.llm_generated_questions = {"questions": questions}
            else:
                if interview.question_mode == "predefined":
                    generated = await llm_service._generate_predefined_questions(
                        context_for_llm,
                        target_count
                    )
                    questions = (generated or [])[:target_count]
                    interview.llm_generated_questions = {"questions": questions}
                else:
                    generated = await llm_service._generate_dynamic_question(context_for_llm)
                    if isinstance(generated, list):
                        questions = generated[:target_count]
                    else:
                        questions = [generated][:target_count]
                    interview.llm_generated_questions = {"questions": questions}
            
            await db.commit()
            
            return {
                "ok": True,
                "questions": questions,
                "mode": interview.question_mode,
                "message": f"Generated {len(questions)} questions successfully (requested {target_count})"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{interview_id}/context")
async def get_context(interview_id: str):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Interview).where(Interview.id == interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            return {
                "ok": True,
                "context": interview.context,
                "mode": interview.question_mode,
                "message": "Context retrieved successfully"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{interview_id}/start")
async def start_interview_session(
    interview_id: str,
    request: StartInterviewRequest
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Interview).where(Interview.id == interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            response = Response(
                interview_id=interview.id,
                name=request.candidate_name,
                email=request.candidate_email
            )
            
            db.add(response)
            await db.commit()
            await db.refresh(response)

            session_id = f"ws_{interview.id}_{response.id}"
            session_token = secrets.token_urlsafe(24)
            try:
                await create_session(session_id)
                await set_session_meta(session_id, {
                    "interview_id": str(interview.id),
                    "response_id": str(response.id),
                    "mode": interview.question_mode,
                    "session_token": session_token,
                    "started_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as redis_err:
                print(f"[ERROR] Redis session init failed: {redis_err}")
            
            return {
                "ok": True,
                "response_id": str(response.id),
                "interview_id": str(interview.id),
                "session_id": session_id,
                "session_token": session_token,
                "mode": interview.question_mode,
                "message": "Interview session started successfully"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{response_id}/current-question")
async def get_current_question(
    response_id: str,
    voice_id: Optional[str] = None
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Response).where(Response.id == response_id))
            response = result.scalar_one_or_none()
            
            if not response:
                raise HTTPException(status_code=404, detail="Response not found")
            
            result = await db.execute(select(Interview).where(Interview.id == response.interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            if interview.question_mode == "predefined":
                if isinstance(interview.llm_generated_questions, list):
                    questions = interview.llm_generated_questions or []
                elif isinstance(interview.llm_generated_questions, dict):
                    questions = interview.llm_generated_questions.get("questions", [])
                else:
                    questions = []

                if not questions and interview.context and (interview.auto_question_generate is True):
                    try:
                        context_for_llm = summarization_service.get_context_for_llm(interview.context)
                        target_count = interview.question_count or 5
                        generated = await llm_service._generate_predefined_questions(context_for_llm, target_count)
                        questions = (generated or [])[:target_count]
                        interview.llm_generated_questions = {"questions": questions}
                        await db.commit()
                    except Exception as gen_err:
                        print(f"[WARN] Failed to auto-generate questions: {gen_err}")
                
                if response.current_question_index < len(questions):
                    current_question = questions[response.current_question_index]
                    result_payload = {
                        "ok": True,
                        "current_question": current_question,
                        "question_number": response.current_question_index + 1,
                        "total_questions": len(questions),
                        "mode": "predefined"
                    }
                    if isinstance(current_question, dict):
                        q_text = current_question.get("question") or current_question.get("text") or ""
                    else:
                        q_text = str(current_question)
                    if q_text:
                        try:
                            audio_bytes = await tts_service.synthesize(q_text, voice_id=voice_id)
                            result_payload["tts_audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
                            result_payload["tts_content_type"] = "audio/mpeg"
                        except Exception as tts_err:
                            print(f"[WARN] TTS failed for predefined: {tts_err}")
                    return result_payload
                else:
                    return {
                        "ok": True,
                        "current_question": None,
                        "interview_complete": True,
                        "mode": "predefined"
                    }
            else:
                if not interview.context:
                    raise HTTPException(status_code=400, detail="No context available")
                
                context_for_llm = summarization_service.get_context_for_llm(interview.context)
                previous_answers = response.qa_history or []
                dynamic_cap = interview.question_count or 0
                if dynamic_cap and response.current_question_index >= dynamic_cap:
                    return {
                        "ok": True,
                        "current_question": None,
                        "interview_complete": True,
                        "mode": "dynamic"
                    }
                
                if response.current_question_index == 0:
                    questions = await llm_service._generate_dynamic_question(context_for_llm)
                    if isinstance(questions, list) and len(questions) > 0:
                        current_question = questions[0]
                    elif isinstance(questions, dict):
                        current_question = questions
                    else:
                        return {
                            "ok": True,
                            "current_question": None,
                            "interview_complete": False,
                            "mode": "dynamic",
                            "message": "No question generated"
                        }
                else:
                    current_question = await llm_service.generate_next_dynamic_question(
                        str(interview.id), 
                        previous_answers
                    )
                
                result_payload = {
                    "ok": True,
                    "current_question": current_question,
                    "question_number": response.current_question_index + 1,
                    "mode": "dynamic"
                }
                if isinstance(current_question, dict):
                    q_text = current_question.get("question") or current_question.get("text") or ""
                else:
                    q_text = str(current_question)
                if q_text:
                    try:
                        audio_bytes = await tts_service.synthesize(q_text, voice_id=voice_id)
                        result_payload["tts_audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
                        result_payload["tts_content_type"] = "audio/mpeg"
                    except Exception as tts_err:
                        print(f"[WARN] TTS failed for dynamic: {tts_err}")
                return result_payload
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{response_id}/submit-answer")
async def submit_answer(
    response_id: str,
    request: SubmitAnswerRequest
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Response).where(Response.id == response_id))
            response = result.scalar_one_or_none()
            
            if not response:
                raise HTTPException(status_code=404, detail="Response not found")
            
            result = await db.execute(select(Interview).where(Interview.id == response.interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            qa_pair = {
                "question": request.question,
                "answer": request.transcript,
                "timestamp": "2024-01-01T00:00:00Z",  
                "analysis": {}  
            }
            
            if not response.qa_history:
                response.qa_history = []
            
            response.qa_history.append(qa_pair)
            response.current_question_index += 1
            
            if interview.question_mode == "dynamic":
                total_questions = interview.question_count or 0
            else:
                if isinstance(interview.llm_generated_questions, list):
                    total_questions = len(interview.llm_generated_questions)
                elif isinstance(interview.llm_generated_questions, dict):
                    total_questions = len(interview.llm_generated_questions.get("questions", []))
                else:
                    total_questions = 0
            
            is_interview_complete = response.current_question_index >= total_questions
                        
            analysis = {}
            if interview.context:
                context_for_llm = summarization_service.get_context_for_llm(interview.context)
                analysis = await llm_service.analyze_response(
                    str(interview.id),
                    request.transcript,
                    {"question": request.question, "expected_answer": "Relevant technical response"}
                )
                qa_pair["analysis"] = analysis
            
            await db.commit()
            
            response_data = {
                "ok": True,
                "answer_submitted": True,
                "question_number": response.current_question_index,
                "analysis": analysis,
                "mode": interview.question_mode,
                "message": "Answer submitted successfully"
            }
            
            if is_interview_complete:
                response_data.update({
                    "interview_completed": True,
                    "total_questions": total_questions,
                    "answered_questions": response.current_question_index,
                    "message": f"All questions completed! Interview finished automatically. {response.current_question_index}/{total_questions} questions answered."
                })
                
                if interview.context:
                    try:
                        final_analysis = await llm_service.generate_final_analysis(
                            str(interview.id),
                            response.qa_history or []
                        )
                        response_data["final_analysis"] = final_analysis
                        response_data["overall_score"] = final_analysis.get("overall_score", 0)
                        response_data["recommendations"] = final_analysis.get("recommendations", [])
                    except Exception as e:
                        print(f"Error generating final analysis: {str(e)}")
                        response_data["final_analysis"] = {"error": "Could not generate final analysis"}
            
            return response_data
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{response_id}/end-interview", response_model=EndInterviewResponse)
async def end_interview_manually(
    response_id: str,
    request: EndInterviewRequest
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Response).where(Response.id == response_id))
            response = result.scalar_one_or_none()
            
            if not response:
                raise HTTPException(status_code=404, detail="Response not found")
            
            result = await db.execute(select(Interview).where(Interview.id == response.interview_id))
            interview = result.scalar_one_or_none()
            
            if not interview:
                raise HTTPException(status_code=404, detail="Interview not found")
            
            if isinstance(interview.llm_generated_questions, list):
                total_questions = len(interview.llm_generated_questions)
            elif isinstance(interview.llm_generated_questions, dict):
                total_questions = len(interview.llm_generated_questions.get("questions", []))
            else:
                total_questions = 0
            
            answered_questions = len(response.qa_history or [])
            
            final_analysis = None
            overall_score = None
            recommendations = []
            
            if answered_questions > 0 and interview.context:
                try:
                    final_analysis = await llm_service.generate_final_analysis(
                        str(interview.id),
                        response.qa_history or []
                    )
                    overall_score = final_analysis.get("overall_score", 0)
                    recommendations = final_analysis.get("recommendations", [])
                except Exception as e:
                    print(f"Error generating final analysis: {str(e)}")
                    final_analysis = {"error": "Could not generate final analysis"}
            
            await db.commit()
            
            return EndInterviewResponse(
                interview_completed=True,
                total_questions=total_questions,
                answered_questions=answered_questions,
                final_analysis=final_analysis,
                overall_score=overall_score,
                recommendations=recommendations,
                message=f"Interview ended manually. {answered_questions}/{total_questions} questions answered."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
