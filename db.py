from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional

# SQLAlchemy setup
DATABASE_URL = "sqlite:///bot_database.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define the User model
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, index=True)
    context = Column(String)
    next_problem = Column(DateTime)
    status = Column(String, default="active")

# Define the Session model
class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    subject = Column(String)
    context = Column(String)
    question = Column(String)
    solving_process = Column(String)
    expected_answer = Column(String)
    attempted = Column(Integer, default=0)
    correct = Column(Boolean, default=False)
    performance_explanation = Column(String)
    performance = Column(Integer)
    completed = Column(Boolean, default=False)
    thread_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Define the SolutionResponse model
class SolutionResponse(Base):
    __tablename__ = 'solution_responses'

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    full_solution = Column(String)
    summarized_solution = Column(String)
    feedback = Column(String)
    is_correct = Column(Boolean)
    performance_explanation = Column(String)
    performance = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def get_user(db, user_id):
    return db.query(User).filter(User.id == user_id).first()

def create_user(db, user_id):
    new_user = User(id=user_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update_user_subject(db, user_id, subject):
    user = get_user(db, user_id)
    if user:
        user.subject = subject
        db.commit()
        db.refresh(user)
    return user

def update_user_context(db, user_id, context):
    user = get_user(db, user_id)
    if user:
        user.context = context
        db.commit()
        db.refresh(user)
    return user

# db.py

def create_session(db: Session, user_id: int, subject: str, context: str, question: str, solving_process: str, expected_answer: str, thread_id : str):
    new_session = Session(
        user_id=user_id,
        subject=subject,
        context=context,
        question=question,
        solving_process=solving_process,
        expected_answer=expected_answer,
        attempted=0,
        correct=False,
        performance_explanation=None,
        performance=None,
        completed=False
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

def get_current_session(db: Session, user_id: int):
    return db.query(Session).filter(
        Session.user_id == user_id,
        Session.completed == False  # Find sessions that are not completed
    ).order_by(Session.created_at.desc()).first()

def update_session(db: Session, session_id: int, **kwargs):
    session = db.query(Session).filter(Session.id == session_id).first()
    if session:
        for key, value in kwargs.items():
            setattr(session, key, value)
        db.commit()
        db.refresh(session)
    return session


def create_solution_response(db: Session, session_id: int, full_solution: str, summarized_solution: str, feedback: str, is_correct: bool, performance_explanation: Optional[str], performance: Optional[int]):
    new_solution_response = SolutionResponse(
        session_id=session_id,
        full_solution=full_solution,
        summarized_solution=summarized_solution,
        feedback=feedback,
        is_correct=is_correct,
        performance_explanation=performance_explanation,
        performance=performance
    )
    db.add(new_solution_response)
    db.commit()
    db.refresh(new_solution_response)
    return new_solution_response

