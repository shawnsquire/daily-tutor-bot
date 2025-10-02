import asyncio
import logging
import os
import traceback

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import BotCommand, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackContext, CommandHandler, ContextTypes, MessageHandler, filters

from src.db import (
    Session,
    TutorSession,
    User,
    create_solution_response,
    create_tutor_session,
    create_user,
    ensure_user_exists,
    get_current_session,
    get_user,
    update_session,
    update_user_memo,
    update_user_subject,
)
from src.openai_handler import (
    chat_generate_question,
    chat_giveup,
    chat_judge_response,
    chat_message,
    chat_play,
    chat_solution_attempt,
)
from src.scheduler import generate_daily_question_for_user, generate_daily_questions
from src.status_server import run_status_server
from src.strings import (
    ADMIN_DELIVERED_DAILY_QUESTION,
    BOT_DESCRIPTION,
    BOT_MENU_GIVE_UP_DESCRIPTION,
    BOT_MENU_HINT_DESCRIPTION,
    BOT_MENU_MEMO_DESCRIPTION,
    BOT_MENU_PLAY_DESCRIPTION,
    BOT_MENU_QUESTION_DESCRIPTION,
    BOT_MENU_SOLVE_DESCRIPTION,
    BOT_MENU_SUBJECT_DESCRIPTION,
    BOT_NAME,
    BOT_SHORT_DESCRIPTION,
    CHECKING_SOLUTION_MESSAGE,
    CURRENT_MEMO_MESSAGE,
    CURRENT_SUBJECT_MESSAGE,
    GENERATING_QUESTION_MESSAGE,
    MEMO_UPDATED_MESSAGE,
    NO_MEMO_MESSAGE,
    NO_SESSION_MESSAGE,
    NO_SUBJECT_MESSAGE,
    PROMPT_SET_SUBJECT_MESSAGE,
    QUESTION_GENERATION_FAILED_MESSAGE,
    QUESTION_READY_MESSAGE,
    START_MESSAGE,
    SUBJECT_SET_MESSAGE,
    SUBMIT_SOLUTION_PROMPT_MESSAGE,
    TUTOR_ERROR_MESSAGE,
)
from src.utils import error_handler, get_db_context, send_typing

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEVELOPER_CHAT_ID = os.getenv("DEVELOPER_CHAT_ID")

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)

# Set the logging level for the httpx and http logger to WARNING or higher
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("http.server").setLevel(logging.WARNING)


def get_user_from_update(update: Update, db: Session | None = None) -> User:
    if db is None:
        db = get_db_context()
    user_id = update.message.from_user.id
    return ensure_user_exists(db, user_id)


# Add a function to update the user's play mode
def update_user_play_mode(db: Session, user_id: int, play_mode: bool) -> None:
    # noinspection PyTypeChecker
    db.query(User).filter(User.id == user_id).update({"status": "playing" if play_mode else "active"})
    db.commit()


def invalidate_old_sessions(db: Session, user_id: int) -> None:
    # Invalidate all the other sessions to not have multiple concurrent
    # noinspection PyTypeChecker
    db.query(TutorSession).filter(TutorSession.user_id == user_id).update({"archived": True}, synchronize_session=False)


# Command: /start
# noinspection PyUnusedLocal
async def start(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = update.message.from_user
    if not get_user(db, user.id):
        create_user(db, user.id)

    # Get the first name from telegram
    user_first_name = update.message.from_user.first_name
    await update.message.reply_text(START_MESSAGE.format(user_first_name=user_first_name))


# Handle /subject command
async def handle_subject(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = get_user_from_update(update, db)

    if context.args:
        # If arguments are provided, update the subject
        subject = " ".join(context.args)
        update_user_subject(db, user.id, subject)
        await update.message.reply_text(SUBJECT_SET_MESSAGE.format(subject=subject))
    else:
        # If no arguments are provided, display the current subject
        if user and user.subject:
            await update.message.reply_text(CURRENT_SUBJECT_MESSAGE.format(subject=user.subject))
        else:
            await update.message.reply_text(NO_SUBJECT_MESSAGE)


# Handle /memo command
async def handle_memo(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = get_user_from_update(update, db)

    if context.args:
        # If arguments are provided, update the context/notes
        memo = " ".join(context.args)
        update_user_memo(db, user.id, memo)
        await update.message.reply_text(MEMO_UPDATED_MESSAGE)
    else:
        # If no arguments are provided, display the current context/notes
        if user and user.memo:
            await update.message.reply_text(CURRENT_MEMO_MESSAGE.format(memo=user.memo))
        else:
            await update.message.reply_text(NO_MEMO_MESSAGE)


# Handle /hint command
async def handle_hint(update: Update, context: CallbackContext) -> None:
    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    db = get_db_context()
    user = get_user_from_update(update, db)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user.id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling the solution attempt
    user_response = "I need a hint."
    response = chat_message(session, user_response, db)

    # Return the feedback to the user
    await update.message.reply_text(response)


# Command: /question
async def generate_new_question(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = get_user_from_update(update, db)

    if not user.subject:
        await update.message.reply_text(PROMPT_SET_SUBJECT_MESSAGE)
        return

    # Let the user know we're getting a question
    await update.message.reply_text(GENERATING_QUESTION_MESSAGE)

    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    # Ask the chat agent for a question
    _, question_data = chat_generate_question(user.subject, user.memo)

    # Alert on an error since we just got text back
    if isinstance(question_data, str):
        await update.message.reply_text(QUESTION_GENERATION_FAILED_MESSAGE)
        return

    # Invalidate all the other sessions to not have multiple concurrent
    invalidate_old_sessions(db, user.id)

    # Disable the user from the schedule
    update_user_play_mode(db, user.id, play_mode=False)

    # Logic to store question and start session
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

    await update.message.reply_text(
        QUESTION_READY_MESSAGE.format(subject=user.subject, question=question_data.question)
    )


# Handle text messages (as solution attempts)
# noinspection DuplicatedCode
async def handle_message(update: Update, context: CallbackContext) -> None:
    await send_typing(update, context)

    db = get_db_context()
    user = get_user_from_update(update, db)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user.id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling the solution attempt
    user_response = update.message.text
    response = chat_message(session, user_response, db)

    # Return the feedback to the user
    await update.message.reply_text(response)


async def handle_solve(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = get_user_from_update(update, db)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user.id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If arguments are provided
    if context.args:
        user_response = " ".join(context.args)
    else:
        await update.message.reply_text(SUBMIT_SOLUTION_PROMPT_MESSAGE)
        return

    # Inform the user we are checking with a judge
    await update.message.reply_text(CHECKING_SOLUTION_MESSAGE)

    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    # If both checks pass, proceed with handling the solution attempt
    response = chat_solution_attempt(session, user_response, db)

    if response is None:
        await update.message.reply_text(TUTOR_ERROR_MESSAGE)

    update_session(
        db,
        session.id,
        attempted=session.attempted + 1,
        correct=response.get("is_correct"),
        completed=response.get("is_correct") or session.completed,
    )

    # Store the solution response in the database
    create_solution_response(
        db,
        session_id=session.id,
        full_solution=response["full_solution"],
        summarized_solution=response["summarized_solution"],
        feedback=response["feedback"],
        is_correct=response["is_correct"],
        performance_explanation=response["performance_explanation"],
        performance=response["performance"],
    )

    # Get a nicer summary of the critical judge
    judge_response = chat_judge_response(session, db)

    # Return the feedback to the user
    await update.message.reply_text(judge_response)


# noinspection DuplicatedCode
async def handle_giveup(update: Update, context: CallbackContext) -> None:
    await send_typing(update, context)

    db = get_db_context()
    user = get_user_from_update(update, db)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user.id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling giving up
    response = chat_giveup(session, db)

    # Mark this as completed because they are done
    update_session(db, session.id, completed=True)

    # Return the feedback to the user
    await update.message.reply_text(response)


async def handle_play(update: Update, context: CallbackContext) -> None:
    await send_typing(update, context)

    db = get_db_context()
    user = get_user_from_update(update, db)

    # Invalidate all the other sessions to not have multiple concurrent
    invalidate_old_sessions(db, user.id)

    # Disable the user from the schedule
    update_user_play_mode(db, user.id, play_mode=True)

    # Create session first so we have an ID
    session = create_tutor_session(
        db=db,
        user_id=user.id,
        subject=user.subject,
        memo=user.memo,
        question="Free conversation mode",
        solving_process="",
        expected_answer="",
        thread_id=None,
    )

    _, response = chat_play(user.subject, user.memo, db, session.id)

    await update.message.reply_markdown(response)


async def handle_send_daily_question(update: Update, context: CallbackContext) -> None:
    db = get_db_context()
    user = get_user_from_update(update, db)

    if not user.is_admin:
        return

    # Typing
    await send_typing(update, context)

    # Get all users, or use provided user IDs
    if len(context.args) == 0:
        await generate_daily_questions(db, context.bot)
        await update.message.reply_text(ADMIN_DELIVERED_DAILY_QUESTION)
        return

    users = [get_user(db, int(x)) for x in context.args]

    tasks = [asyncio.create_task(generate_daily_question_for_user(db, context.bot, user)) for user in users]
    await asyncio.gather(*tasks)

    # Notify admin of successes and failures
    await update.message.reply_text(ADMIN_DELIVERED_DAILY_QUESTION)


# Error handler
async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.warning(f"Update {update} caused error {context.error}.\n\n{tb_string}")
    error_handler(update, context)

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=f"Update {update} caused error {context.error}.\n\n{tb_string}"
    )

    # noinspection PyUnresolvedReferences
    await update.message.reply_text(TUTOR_ERROR_MESSAGE)


async def post_init(application: Application) -> None:
    # Menu builder
    menu = [
        BotCommand(command="subject", description=BOT_MENU_SUBJECT_DESCRIPTION),
        BotCommand(command="memo", description=BOT_MENU_MEMO_DESCRIPTION),
        BotCommand(command="hint", description=BOT_MENU_HINT_DESCRIPTION),
        BotCommand(command="question", description=BOT_MENU_QUESTION_DESCRIPTION),
        BotCommand(command="solve", description=BOT_MENU_SOLVE_DESCRIPTION),
        BotCommand(command="giveup", description=BOT_MENU_GIVE_UP_DESCRIPTION),
        BotCommand(command="freetalk", description=BOT_MENU_PLAY_DESCRIPTION),
    ]

    # noinspection PyUnresolvedReferences
    await application.bot.set_my_commands(menu)


# noinspection PyUnresolvedReferences
async def define_bot(application: Application) -> None:
    await application.bot.set_my_name(BOT_NAME)
    await application.bot.set_my_description(BOT_DESCRIPTION)
    await application.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)


def create_bot() -> Application:
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True).post_init(post_init).build()

    # Handlers
    application.add_handler(CommandHandler("start", start, block=False))
    application.add_handler(CommandHandler("subject", handle_subject, block=False))
    application.add_handler(CommandHandler("memo", handle_memo, block=False))
    application.add_handler(CommandHandler("hint", handle_hint, block=False))
    application.add_handler(CommandHandler("question", generate_new_question, block=False))
    application.add_handler(CommandHandler("solve", handle_solve, block=False))
    application.add_handler(CommandHandler("giveup", handle_giveup, block=False))
    application.add_handler(CommandHandler("freetalk", handle_play, block=False))

    # Admin handlers
    # Add a hidden slash command to trigger the daily question generation
    application.add_handler(CommandHandler("daily_question", handle_send_daily_question, block=False))

    # Message handler for non-command text (solution attempts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message, block=False))

    # Error handler
    application.add_error_handler(handle_error)

    return application


def run_bot(application: Application) -> None:
    # Start the Bot
    application.run_polling()


async def run_scheduler(application: Application) -> None:
    # Create an AsyncIOScheduler instance
    scheduler = AsyncIOScheduler()

    # Schedule the generate_daily_questions function to run daily at 8am EST
    # TODO: Run every minute and check when the user is scheduled to recieve theirs?
    scheduler.add_job(
        generate_daily_questions,
        "cron",
        hour=15,
        minute=00,
        timezone=pytz.timezone("US/Eastern"),
        args=[get_db_context(), application],
    )

    scheduler.start()


async def run_status() -> None:
    # Run the status server in a separate thread
    run_status_server()


def main_bot_only() -> None:
    # We need the bot to start up before we can continue
    application = create_bot()
    run_bot(application)


async def main() -> None:
    # We need the bot to start up before we can continue
    application = create_bot()

    # List to hold only successful tasks
    tasks = []

    # Start the scheduler in the background
    try:
        scheduler_task = asyncio.create_task(run_scheduler(application))
        tasks.append(scheduler_task)
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    # Start the status server in the background
    try:
        status_task = asyncio.create_task(run_status())
        tasks.append(status_task)
    except Exception as e:
        logger.error(f"Failed to start status server: {e}")

    # Define the bot properties
    tasks.append(asyncio.create_task(define_bot(application)))

    # Wait for all tasks to finish
    await asyncio.gather(*tasks)

    # Run the bot
    run_bot(application)


if __name__ == "__main__":
    # asyncio.run(main())
    main_bot_only()
