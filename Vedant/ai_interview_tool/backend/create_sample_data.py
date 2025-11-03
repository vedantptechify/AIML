# Script to create sample interview data for testing

import os
import asyncio
import uuid
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base, Organization, User, Interview, Response, Feedback

load_dotenv()

engine = create_async_engine(os.getenv("DATABASE_URL"), echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_sample_data():
    async with AsyncSessionLocal() as session:
        # Create sample organization
        # org = Organization(
        #     id=str(uuid.uuid4()),
        #     name="Sample Organization",
        #     allowed_responses_count=100
        # )
        # session.add(org)
        # await session.flush()  # Get the org ID
        
        # # Create sample user
        # user = User(
        #     id=str(uuid.uuid4()),
        #     email="admin@sample.com",
        #     role="admin",
        #     organization_id=org.id
        # )
        # session.add(user)
        # await session.flush()  # Get the user ID
        
        # # Create sample interview
        # interview = Interview(
        #     id=str(uuid.uuid4()),
        #     name="Sample Interview",
        #     description="A sample interview for testing purposes",
        #     objective="Test the interview system functionality",
        #     organization_id=org.id,
        #     user_id=user.id,
        #     is_active=True,
        #     questions=[
        #         {
        #             "id": "q1",
        #             "text": "Tell me about yourself",
        #             "type": "text",
        #             "duration": 120
        #         },
        #         {
        #             "id": "q2", 
        #             "text": "What are your strengths?",
        #             "type": "text",
        #             "duration": 90
        #         }
        #     ],
        #     question_count=2,
        #     response_count=0,
        #     time_duration="5 minutes"
        # )
        # session.add(interview)
        # await session.commit()

        new_response = Response(
            id=str(uuid.uuid4()),
            interview_id="cb0baa17-fb00-4523-a713-77247f8d89c6",
            name="Luffy",
            email="luffy@email.com",
            call_id="123",
            transcripts=[],
            is_ended=False,
            is_analysed=False,
            is_viewed=False
        )
        session.add(new_response)
        await session.commit()
        
        # print(f"✅ Created sample data:")
        # print(f"   Organization ID: {org.id}")
        # print(f"   User ID: {user.id}")
        # print(f"   Interview ID: {interview.id}")
        # print(f"   Interview Name: {interview.name}")
        # print(f"\n🎯 Use this Interview ID in your frontend: {interview.id}")

if __name__ == "__main__":
    asyncio.run(create_sample_data())