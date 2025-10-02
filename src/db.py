import os
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Postgres setup
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")

engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Define the User model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, index=True)
    memo = Column(String)
    next_problem = Column(DateTime)
    status = Column(String, default="active")
    is_admin = Column(Boolean, default=False)


# Define the Session model
class TutorSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    subject = Column(String)
    memo = Column(String)
    question = Column(String)
    solving_process = Column(String)
    expected_answer = Column(String)
    attempted = Column(Integer, default=0)
    correct = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)
    performance_explanation = Column(String)
    performance = Column(Integer)
    completed = Column(Boolean, default=False)
    thread_id = Column(String)
    created_at = Column(DateTime, default=datetime.now(UTC))
    updated_at = Column(DateTime, default=datetime.now(UTC))


# Define the SolutionResponse model
class SolutionResponse(Base):
    __tablename__ = "solution_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    full_solution = Column(String)
    summarized_solution = Column(String)
    feedback = Column(String)
    is_correct = Column(Boolean)
    performance_explanation = Column(String)
    performance = Column(Integer)
    created_at = Column(DateTime, default=datetime.now(UTC))


# Define the Message model for conversation history
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    role = Column(String)  # 'system', 'user', 'assistant'
    content = Column(String)
    created_at = Column(DateTime, default=datetime.now(UTC))


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


def get_all_users(db):
    return db.query(User).all()


def get_all_users_with_subject(db):
    return db.query(User).filter(User.subject.is_not(None)).all()


def create_user(db, user_id):
    new_user = User(id=user_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# Ensure user exists or create one
def ensure_user_exists(db: Session, user_id: int):
    user = get_user(db, user_id)
    if not user:
        user = create_user(db, user_id)
    return user


def update_user_subject(db, user_id, subject):
    user = get_user(db, user_id)
    if user:
        user.subject = subject
        db.commit()
        db.refresh(user)
    return user


def update_user_memo(db, user_id, memo):
    user = get_user(db, user_id)
    if user:
        user.memo = memo
        db.commit()
        db.refresh(user)
    return user


def create_tutor_session(
    db: Session,
    user_id: int,
    subject: str,
    memo: str,
    question: str,
    solving_process: str,
    expected_answer: str,
    thread_id: str,
):
    new_session = TutorSession(
        user_id=user_id,
        subject=subject,
        memo=memo,
        question=question,
        solving_process=solving_process,
        expected_answer=expected_answer,
        thread_id=thread_id,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


# noinspection PyTypeChecker
def get_current_session(db: Session, user_id: int):
    session = (
        db.query(TutorSession)
        .filter(TutorSession.user_id == user_id, ~TutorSession.archived)
        .order_by(TutorSession.created_at.desc())
        .first()
    )
    if session is None:
        raise ValueError(f"No current session found for user {user_id}")
    return session


# noinspection PyTypeChecker
def update_session(db: Session, session_id: int, **kwargs):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if session:
        for key, value in kwargs.items():
            setattr(session, key, value)
        db.commit()
        db.refresh(session)
    return session


def create_solution_response(
    db: Session,
    session_id: int,
    full_solution: str,
    summarized_solution: str,
    feedback: str,
    is_correct: bool,
    performance_explanation: str | None,
    performance: int | None,
):
    new_solution_response = SolutionResponse(
        session_id=session_id,
        full_solution=full_solution,
        summarized_solution=summarized_solution,
        feedback=feedback,
        is_correct=is_correct,
        performance_explanation=performance_explanation,
        performance=performance,
    )
    db.add(new_solution_response)
    db.commit()
    db.refresh(new_solution_response)
    return new_solution_response


def create_message(db: Session, session_id: int, role: str, content: str):
    new_message = Message(session_id=session_id, role=role, content=content)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message


def get_session_messages(db: Session, session_id: int):
    return db.query(Message).filter(Message.session_id == session_id).order_by(Message.created_at).all()
