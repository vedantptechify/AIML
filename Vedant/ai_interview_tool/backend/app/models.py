# SQLAlchemy models

import uuid
import enum
from datetime import datetime
from sqlalchemy import (create_engine, Column,String,Integer,FLOAT,Text,Boolean,DateTime,ForeignKey,Enum,JSON,ARRAY,TIMESTAMP,func)
from sqlalchemy.dialects.postgresql import JSONB,UUID
from sqlalchemy.orm import declarative_base,relationship

Base = declarative_base()

class PlanEnum(enum.Enum):
    free = "free"
    pro = "pro"
    free_trial_over = "free_trial_over"

class Organization(Base):
    __tablename__ = "organization"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    name = Column(Text)
    image_url = Column(Text)
    allowed_responses_count = Column(Integer)
    plan = Column(Enum(PlanEnum), nullable=False, default=PlanEnum.free)  
   
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    email = Column(Text)
    role = Column(String, nullable=False, default="user")
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"))

    organization = relationship("Organization", back_populates="users")
    interviews = relationship("Interview", back_populates="user", cascade="all, delete-orphan")

class Interview(Base):
    __tablename__ = "interview"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    name = Column(Text)
    description = Column(Text)
    objective = Column(Text)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"))
    is_active = Column(Boolean, default=True)
    is_anonymous = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    logo_url = Column(Text)
    theme_color = Column(Text)
    url = Column(Text)
    readable_slug = Column(Text)
    questions = Column(JSONB)
    quotes = Column(ARRAY(JSONB))
    insights = Column(ARRAY(Text))
    respondents = Column(ARRAY(Text))
    question_count = Column(Integer)
    response_count = Column(Integer)
    time_duration = Column(Text)
    job_description = Column(Text)
    required_skills = Column(ARRAY(Text))
    experience_level = Column(Text)
    llm_generated_questions = Column(JSONB)
    interview_flow = Column(JSONB)
    dynamic_context = Column(JSONB)
    context = Column(JSONB, default={})  
    question_mode = Column(String, default="predefined")  
    auto_question_generate = Column(Boolean, default=True)
    manual_questions = Column(JSONB)

    organization = relationship("Organization", back_populates="interviews")
    user = relationship("User", back_populates="interviews")
    responses = relationship("Response", back_populates="interview", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="interview", cascade="all, delete-orphan")

class Response(Base):
    __tablename__ = "response"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interview.id"))
    name = Column(Text)
    email = Column(Text)
    start_time = Column(TIMESTAMP(timezone=True))
    end_time = Column(TIMESTAMP(timezone=True))
    interview_session_id = Column(String, unique=True)
    current_question_index = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    qa_history = Column(JSONB, default=[])  
    duration = Column(Integer)  
    video_chunks_count = Column(Integer, default=0)
    question_audio_count = Column(Integer, default=0)

    interview = relationship("Interview", back_populates="responses")

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interview.id"))
    email = Column(Text)
    feedback = Column(Text)
    satisfaction = Column(Integer)
    
    interview = relationship("Interview", back_populates="feedbacks")
