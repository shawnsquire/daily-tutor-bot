import asyncio

from telegram.ext import ExtBot as Bot

from src.db import User, create_tutor_session, get_all_users_with_subject
from src.openai_handler import chat_generate_question
from src.strings import QUESTION_READY_MESSAGE


async def generate_daily_question_for_user(db, bot: Bot, user: User) -> None:
    if user.subject is None:
        return

    _, question_data = chat_generate_question(user.subject, user.memo)
    if not isinstance(question_data, str):
        create_tutor_session(
            db=db,
            user_id=user.id,
            subject=user.subject,
            memo=user.memo,
            question=question_data.question,
            solving_process=question_data.solving_process,
            expected_answer=question_data.expected_answer,
            thread_id=None,
        )

        await bot.send_message(
            user.id, QUESTION_READY_MESSAGE.format(subject=user.subject, question=question_data.question)
        )


async def generate_daily_questions(db, bot: Bot):
    users = get_all_users_with_subject(db)
    tasks = [asyncio.create_task(generate_daily_question_for_user(db, bot, user)) for user in users]
    await asyncio.gather(*tasks)
