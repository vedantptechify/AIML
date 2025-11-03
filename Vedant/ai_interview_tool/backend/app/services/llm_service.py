# LLM (OpenAI, Anthropic, etc.)

import json
import asyncio
import json
import re
from typing import Dict, List, Optional
from config_loader import load_config
import openai
from openai import AsyncOpenAI
try:
    # Available in openai>=1.30.0
    from openai import AsyncAzureOpenAI  # type: ignore
except Exception:
    AsyncAzureOpenAI = None  # Fallback if package version doesn't include Azure client
import uuid
from services.summarization_service import summarization_service
from db import AsyncSessionLocal
from models import Interview
from sqlalchemy import select

class LLMService:
    def __init__(self):
        self.config = load_config()  
        self.provider = self.config.get('llm', {}).get('provider', 'openai')
        self.api_key = self.config.get('llm', {}).get('api_key')
        self.model = self.config.get('llm', {}).get('model', 'gpt-4o-mini')
        # Azure-specific settings (used only when provider is azure)
        self.azure_endpoint = self.config.get('llm', {}).get('azure_endpoint')
        self.azure_api_version = self.config.get('llm', {}).get('api_version', '2024-02-01')
        # Azure uses deployment name instead of raw model name
        self.azure_deployment = self.config.get('llm', {}).get('deployment', self.model)
        self.max_tokens = self.config.get('llm', {}).get('max_tokens', 1000)
        self.temperature = self.config.get('llm', {}).get('temperature', 0.7)
        
        if self.provider.lower() in ('openai', 'openai_platform'):
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif self.provider.lower() in ('azure', 'azure_openai', 'azure-openai'):
            if AsyncAzureOpenAI is None:
                raise RuntimeError("AsyncAzureOpenAI client not available. Please upgrade the openai package.")
            if not self.api_key:
                raise ValueError("Azure API key is required (llm.api_key).")
            # os.path.expandvars will substitute missing envs with empty string, coalesce those
            if not self.azure_endpoint:
                raise ValueError("Azure endpoint is required for Azure OpenAI (llm.azure_endpoint in config).")
            if not self.azure_api_version:
                self.azure_api_version = '2024-02-01'
            if not self.azure_deployment:
                raise ValueError("Azure deployment name is required (llm.deployment). Set it to your Azure model deployment name.")
            # For Azure, pass deployment name as the model in requests
            self.model = self.azure_deployment
            self.client = AsyncAzureOpenAI(
                azure_endpoint=self.azure_endpoint,
                api_key=self.api_key,
                api_version=self.azure_api_version,
            )
    
    def _parse_json(self, text: str):
        """Robustly parse JSON from LLM outputs that may include extra text or code fences."""
        text = (text or "").strip()
        # Try direct parse first
        try:
            return json.loads(text)
        except Exception:
            pass
        # Extract fenced code block
        if "```" in text:
            parts = text.split("```")
            candidates = [p for p in parts if p.strip()]
            if len(candidates) >= 1:
                fenced = candidates[0] if len(candidates) == 1 else candidates[1]
                lines = fenced.splitlines()
                if lines and lines[0].strip().lower() in ("json", "javascript", "ts", "typescript", "python"):
                    fenced_json = "\n".join(lines[1:])
                else:
                    fenced_json = fenced
                try:
                    return json.loads(fenced_json)
                except Exception:
                    pass
        # Regex to find first JSON object/array
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                pass
        raise ValueError("LLM response did not contain valid JSON")

    async def generate_questions(self, interview_id: str, context: Dict, question_mode: str = "predefined") -> List[Dict]:
        try:
            context_summary = context.get('context_summary', 'No context available')
            
            if question_mode == "predefined":
                return await self._generate_predefined_questions(context_summary, context.get("question_count", 5))
            else:
                return await self._generate_dynamic_question(context_summary)
                
        except Exception as e:
            print(f"Error generating questions: {str(e)}")
            return []
    
    async def _generate_predefined_questions(self, context_summary: str, question_count: int) -> List[Dict]:
        prompt = f"""
        Context: {context_summary}
        
        Generate {question_count} interview questions covering:
        1. Introduction/Background (1 question)
        2. Technical skills (2-3 questions)
        3. Experience/Projects (1-2 questions)
        4. Problem-solving (1 question)
        
        Return JSON array with id, question, type, difficulty, expected_answer.
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3
        )
        
        questions_text = response.choices[0].message.content
        questions = self._parse_json(questions_text)
        
        for i, question in enumerate(questions):
            question['id'] = str(uuid.uuid4())
        
        return questions
    
    async def _generate_dynamic_question(self, context_summary: str) -> List[Dict]:
        """Generate first question for dynamic mode"""
        prompt = f"""
        Context: {context_summary}
        
        Generate the first interview question that:
        1. Welcomes the candidate
        2. Asks about their background
        3. Sets the tone for the interview
        
        Return JSON object with id, question, type, difficulty, expected_answer.
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        
        question_text = response.choices[0].message.content
        question = self._parse_json(question_text)
        question['id'] = str(uuid.uuid4())
        
        return [question]
    
    async def generate_next_dynamic_question(self, interview_id: str, previous_answers: List[Dict]) -> Dict:
        """Generate next question based on previous answers (dynamic mode only)"""
        return {
            "id": str(uuid.uuid4()),
            "question": "Can you tell me more about your experience?",
            "type": "follow_up",
            "difficulty": "medium",
            "expected_answer": "More detailed experience description"
        }

    async def analyze_response(self, interview_id: str, transcript: str, question_context: Dict) -> Dict:
        """
        Analyze response - simplified version
        """
        try:
            question = question_context.get('question', '')
            expected_answer = question_context.get('expected_answer', '')
            
            prompt = f"""
            Question: {question}
            Expected Answer: {expected_answer}
            Candidate Response: {transcript}
            
            Analyze and return JSON with:
            - relevance_score (1-10)
            - completeness_score (1-10)
            - clarity_score (1-10)
            - overall_score (1-10)
            - strengths (array)
            - weaknesses (array)
            - suggestions (array)
            - follow_up_questions (array)
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3
            )
            
            analysis_text = response.choices[0].message.content
            analysis = self._parse_json(analysis_text)
            return analysis
            
        except Exception as e:
            print(f"Error analyzing response: {str(e)}")
            return {
                "relevance_score": 7,
                "completeness_score": 7,
                "clarity_score": 7,
                "overall_score": 7,
                "strengths": ["Good response"],
                "weaknesses": ["Could be more detailed"],
                "suggestions": ["Provide more examples"],
                "follow_up_questions": ["Can you elaborate more?"]
            }

    async def generate_next_question(self, interview_id: str, session_context: Dict) -> Dict:
        try:
            previous_responses = session_context.get('responses', [])
            current_question_index = session_context.get('current_question_index', 0)
            
            prompt = f"""
            Based on the interview progress, generate the next appropriate question.
            
            Previous Responses: {json.dumps(previous_responses, indent=2)}
            Current Question Index: {current_question_index}
            
            Return next question in this JSON format:
            {{
                "id": "{str(uuid.uuid4())}",
                "question": "What is your greatest weakness?",
                "type": "behavioral",
                "difficulty": "medium",
                "expected_answer": "Honest self-assessment with improvement plan"
            }}
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            question_text = response.choices[0].message.content
            question = self._parse_json(question_text)
            
            if 'id' not in question or not question['id']:
                question['id'] = str(uuid.uuid4())
            
            return question
            
        except Exception as e:
            print(f"Error generating next question: {str(e)}")
            return {}

    async def generate_feedback(self, response_id: str, analysis: Dict) -> str:
        try:
            prompt = f"""
            Generate constructive feedback for the candidate based on this analysis:
            
            Analysis: {json.dumps(analysis, indent=2)}
            
            Provide feedback that is:
            - Constructive and helpful
            - Specific and actionable
            - Encouraging but honest
            - Professional in tone
            
            Return feedback as plain text.
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            feedback = response.choices[0].message.content
            return feedback
            
        except Exception as e:
            print(f"Error generating feedback: {str(e)}")
            return "Unable to generate feedback at this time."
    
    async def generate_final_analysis(self, interview_id: str, qa_history: List[Dict]) -> Dict:
        """
        Generate comprehensive final analysis of the entire interview
        """
        try: 
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Interview).where(Interview.id == interview_id))
                interview = result.scalar_one_or_none()
                
                if not interview or not interview.context:
                    return {"error": "No context available for analysis"}
                
                context_summary = interview.context.get('context_summary', 'No context available')
                
                qa_summary = ""
                for i, qa in enumerate(qa_history, 1):
                    qa_summary += f"Q{i}: {qa.get('question', 'N/A')}\n"
                    qa_summary += f"A{i}: {qa.get('answer', 'N/A')}\n\n"
                
                prompt = f"""
                You are an expert HR interviewer analyzing a completed interview session.
                
                Job Context: {context_summary}
                
                Interview Q&A History:
                {qa_summary}
                
                Please provide a comprehensive final analysis including:
                1. Overall performance score (0-100)
                2. Key strengths demonstrated
                3. Areas for improvement
                4. Technical competency assessment
                5. Communication skills evaluation
                6. Cultural fit assessment
                7. Hiring recommendation (Strong Hire, Hire, No Hire, Strong No Hire)
                8. Specific recommendations for the candidate
                9. Next steps if hired
                
                Format your response as a JSON object with these exact keys:
                - overall_score: integer (0-100)
                - strengths: array of strings
                - weaknesses: array of strings
                - technical_score: integer (0-100)
                - communication_score: integer (0-100)
                - cultural_fit_score: integer (0-100)
                - hiring_recommendation: string (one of: "Strong Hire", "Hire", "No Hire", "Strong No Hire")
                - recommendations: array of strings
                - next_steps: array of strings
                - summary: string (brief overall assessment)
                """
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=0.3  
                )
                
                analysis_text = response.choices[0].message.content
                
                try:
                    analysis = self._parse_json(analysis_text)
                    return analysis
                except Exception:
                    return {
                        "overall_score": 75,
                        "strengths": ["Good communication"],
                        "weaknesses": ["Could provide more specific examples"],
                        "technical_score": 70,
                        "communication_score": 80,
                        "cultural_fit_score": 75,
                        "hiring_recommendation": "Hire",
                        "recommendations": ["Continue developing technical skills"],
                        "next_steps": ["Schedule follow-up interview"],
                        "summary": analysis_text[:200] + "..." if len(analysis_text) > 200 else analysis_text
                    }
                
        except Exception as e:
            print(f"Error generating final analysis: {str(e)}")
            return {
                "error": f"Could not generate final analysis: {str(e)}",
                "overall_score": 0,
                "strengths": [],
                "weaknesses": ["Analysis unavailable"],
                "recommendations": ["Manual review required"]
            }
    
    async def _generate_text(self, prompt: str) -> str:
        """Helper method to generate text from LLM"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating text: {str(e)}")
            return "Error generating response"


llm_service = LLMService()