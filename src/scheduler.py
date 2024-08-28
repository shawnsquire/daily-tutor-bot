from src.db import get_all_users, create_tutor_session
from src.openai_handler import chat_generate_question
from telegram.ext import ExtBot as Bot
import asyncio
from src.strings import QUESTION_READY_MESSAGE
from src.db import User

async def generate_daily_question_for_user(db, bot: Bot, user: User):
    thread_id, question_data = chat_generate_question(user.subject, user.memo)
    if not isinstance(question_data, str):
        create_tutor_session(
            db=db,
            user_id=user.id,
            subject=user.subject,
            memo=user.memo,
            question=question_data.question,
            solving_process=question_data.solving_process,
            expected_answer=question_data.expected_answer,
            thread_id=thread_id
        )

    await bot.send_message(user.id, QUESTION_READY_MESSAGE.format(subject=user.subject, question=question_data.question))

async def generate_daily_questions(db, bot: Bot):
    users = get_all_users(db)
    tasks = [asyncio.create_task(generate_daily_question_for_user(db, bot, user)) for user in users]
    await asyncio.gather(*tasks)