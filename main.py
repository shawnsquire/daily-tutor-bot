import os
import logging
import traceback
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from db import *
from openai_handler import chat_generate_question, chat_message, chat_solution_attempt, chat_judge_response
from utils import error_handler
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


class GetUpdatesFilter(logging.Filter):
    def filter(self, record):
        # Check if the log message contains both 'getUpdates' and 'api.telegram.org'
        message = record.getMessage()
        if "getUpdates" in message and "api.telegram.org" in message:
            return False  # Filter out this message
        return True  # Allow other messages


logger.addFilter(GetUpdatesFilter())


# Dependency for the database session
def get_db_context(context: CallbackContext) -> Session:
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
        create_user(user.id)
    await update.message.reply_text('Welcome! Please set your subject with /subject "Your Subject"')

# Handle /subject command
async def handle_subject(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if context.args:
        # If arguments are provided, update the subject
        subject = ' '.join(context.args)
        update_user_subject(db, user_id, subject)
        await update.message.reply_text(f'Subject set to: {subject}')
    else:
        # If no arguments are provided, display the current subject
        if user and user.subject:
            await update.message.reply_text(f'Your current subject is: {user.subject}')
        else:
            await update.message.reply_text('No subject set. Please set your subject using /subject "Your Subject".')

# Handle /notes command
async def handle_notes(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if context.args:
        # If arguments are provided, update the context/notes
        notes = ' '.join(context.args)
        update_user_context(db, user_id, notes)
        await update.message.reply_text('Context updated.')
    else:
        # If no arguments are provided, display the current context/notes
        if user and user.context:
            await update.message.reply_text(f'Your current context is: {user.context}')
        else:
            await update.message.reply_text('No context set. Please set your context using /notes "Your Context".')

# Command: /question
async def generate_new_question(update: Update, context: CallbackContext) -> None:
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')

    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    if not user.subject:
        await update.message.reply_text('Please set a subject first using /subject.')
        return

    # Let the user know we're getting a question
    await update.message.reply_text('Generating a question for you, one second...')

    # Ask the chat agent for a question
    thread_id, question_data = chat_generate_question(user.subject, user.context)

    if isinstance(question_data, str):
        await update.message.reply_text(question_data)
        return

    # Logic to store question and start session
    new_session = create_session(
        db=db,
        user_id=user_id,
        subject=user.subject,
        context=user.context,
        question=question_data.question,
        solving_process=question_data.solving_process,
        expected_answer=question_data.expected_answer,
        thread_id=thread_id
    )

    await update.message.reply_text(f'Your question: {question_data.question}')

# Handle text messages (as solution attempts)
async def handle_message(update: Update, context: CallbackContext) -> None:
    db = get_db_context(context)
    user_id = update.message.from_user.id
    user = ensure_user_exists(db, user_id)

    # Check if the user has set a subject
    if not user.subject:
        await update.message.reply_text('Please set your subject first using /subject.')
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text('No active session found. Please start a new session with /question.')
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
        await update.message.reply_text('Please set your subject first using /subject.')
        return

    # Check if there is an active session
    session = get_current_session(db, user_id)
    if not session:
        await update.message.reply_text("You don't have a question yet to solve!")
        return

    # If arguments are provided
    if context.args:
        user_response = ' '.join(context.args)
    else:
        await update.message.reply_text("Make sure you submit an answer with /solve")
        return

    # Inform the user we are checking with a judge
    await update.message.reply_text("Thanks! Let me submit your answer to the judge...")

    # If both checks pass, proceed with handling the solution attempt
    response = chat_solution_attempt(session, user_response)

    if response.get("is_correct"):
        update_session(db, session.id, attempted=session.attempted + 1, correct=response.get("is_correct"))

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

# Error handler
async def handle_error(update: Update, context: CallbackContext) -> None:
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.warning(f'Update {update} caused error {context.error}.\n\n{tb_string}')
    error_handler(update, context)

    await update.message.reply_text('An error occurred. Please try again later.')

def main() -> None:
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subject", handle_subject))
    application.add_handler(CommandHandler("notes", handle_notes))
    application.add_handler(CommandHandler("question", generate_new_question))
    application.add_handler(CommandHandler("solve", handle_solve))

    # Message handler for non-command text (solution attempts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(handle_error)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()

