import os
import logging
import traceback
from telegram import Update, BotCommand
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from src.db import *
from src.strings import *
from src.openai_handler import chat_generate_question, chat_message, chat_solution_attempt, chat_judge_response, chat_giveup
from src.utils import error_handler
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Set the logging level for the httpx logger to WARNING or higher
logging.getLogger('httpx').setLevel(logging.WARNING)


# Dependency for the database session
def get_db_context(context: CallbackContext) -> Session:
    # We may choose to use the CallbackContext to get the database session
    # For now, though, we expect only one database
    return next(get_db())

# Ensure user exists or create one
def ensure_user_exists(db: Session, user_id: int):
    user = get_user(db, user_id)
    if not user:
        user = create_user(db, user_id)
    return user

# Command: /start
async def start(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user = update.message.from_user
    if not get_user(db, user.id):
        create_user(db, user.id)

    # Get the first name from telegram
    user_first_name =  update.message.from_user.first_name
    await update.message.reply_text(START_MESSAGE.format(user_first_name=user_first_name))

# Handle /subject command
async def handle_subject(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if context.args:
        # If arguments are provided, update the subject
        subject = ' '.join(context.args)
        update_user_subject(db, user_id, subject)
        await update.message.reply_text(SUBJECT_SET_MESSAGE.format(subject=subject))
    else:
        # If no arguments are provided, display the current subject
        if user and user.subject:
            await update.message.reply_text(CURRENT_SUBJECT_MESSAGE.format(subject=user.subject))
        else:
            await update.message.reply_text(NO_SUBJECT_MESSAGE)

# Handle /memo command
async def handle_memo(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if context.args:
        # If arguments are provided, update the context/notes
        memo = ' '.join(context.args)
        update_user_memo(db, user_id, memo)
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

    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling the solution attempt
    user_response = "I need a hint."
    response = chat_message(session, user_response)

    # Return the feedback to the user
    await update.message.reply_text(response)

# Command: /question
async def generate_new_question(update: Update, context: CallbackContext) -> None:

    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if not user.subject:
        await update.message.reply_text(PROMPT_SET_SUBJECT_MESSAGE)
        return

    # Let the user know we're getting a question
    await update.message.reply_text(GENERATING_QUESTION_MESSAGE)

    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    # Ask the chat agent for a question
    thread_id, question_data = chat_generate_question(user.subject, user.memo)

    if isinstance(question_data, str):
        await update.message.reply_text(QUESTION_GENERATION_FAILED_MESSAGE)
        return

    # Logic to store question and start session
    create_tutor_session(
        db=db,
        user_id=user_id,
        subject=user.subject,
        memo=user.memo,
        question=question_data.question,
        solving_process=question_data.solving_process,
        expected_answer=question_data.expected_answer,
        thread_id=thread_id
    )

    await update.message.reply_text(QUESTION_READY_MESSAGE.format(question=question_data.question))

# Handle text messages (as solution attempts)
async def handle_message(update: Update, context: CallbackContext) -> None:
    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling the solution attempt
    user_response = update.message.text
    response = chat_message(session, user_response)

    # Return the feedback to the user
    await update.message.reply_text(response)

async def handle_solve(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If arguments are provided
    if context.args:
        user_response = ' '.join(context.args)
    else:
        await update.message.reply_text(SUBMIT_SOLUTION_PROMPT_MESSAGE)
        return

    # Inform the user we are checking with a judge
    await update.message.reply_text(CHECKING_SOLUTION_MESSAGE)

    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    # If both checks pass, proceed with handling the solution attempt
    response = chat_solution_attempt(session, user_response)

    update_session(db, session.id, attempted=session.attempted + 1,
                   correct=response.get("is_correct"),
                   completed=response.get("is_correct") or session.completed)

    # Store the solution response in the database
    create_solution_response(
        db,
        session_id=session.id,
        full_solution=response["full_solution"],
        summarized_solution=response["summarized_solution"],
        feedback=response["feedback"],
        is_correct=response["is_correct"],
        performance_explanation=response["performance_explanation"],
        performance=response["performance"]
    )

    # Get a nicer summary of the critical judge
    judge_response = chat_judge_response(session)

    # Return the feedback to the user
    await update.message.reply_text(judge_response)

async def handle_giveup(update: Update, context: CallbackContext) -> None:
    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)

    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text(NO_SUBJECT_MESSAGE)
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text(NO_SESSION_MESSAGE)
        return

    # If both checks pass, proceed with handling giving up
    response = chat_giveup(session)

    # Mark this as completed because they are done
    update_session(db, session.id, completed=True)

    # Return the feedback to the user
    await update.message.reply_text(response)

# Error handler
async def handle_error(update: Update, context: CallbackContext) -> None:
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.warning(f'Update {update} caused error {context.error}.\n\n{tb_string}')
    error_handler(update, context)

    await update.message.reply_text(TUTOR_ERROR_MESSAGE)

async def post_init(application: Application) -> None:
    # Menu builder
    menu = [
        BotCommand(command='subject', description=BOT_MENU_SUBJECT_DESCRIPTION),
        BotCommand(command='memo', description=BOT_MENU_MEMO_DESCRIPTION),
        BotCommand(command='hint', description=BOT_MENU_HINT_DESCRIPTION),
        BotCommand(command='question', description=BOT_MENU_QUESTION_DESCRIPTION),
        BotCommand(command='solve', description=BOT_MENU_SOLVE_DESCRIPTION),
        BotCommand(command='giveup', description=BOT_MENU_GIVE_UP_DESCRIPTION)
    ]

    await application.bot.set_my_commands(menu)

def main() -> None:
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subject", handle_subject))
    application.add_handler(CommandHandler("memo", handle_memo))
    application.add_handler(CommandHandler("hint", handle_hint))
    application.add_handler(CommandHandler("question", generate_new_question))
    application.add_handler(CommandHandler("solve", handle_solve))
    application.add_handler(CommandHandler("giveup", handle_giveup))

    # Message handler for non-command text (solution attempts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(handle_error)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()

