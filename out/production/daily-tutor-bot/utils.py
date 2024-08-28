import logging
from sqlalchemy.orm import Session
from src.db import get_db
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

def error_handler(update, context):
    logging.error(f"Update {update} caused error {context.error}")

# Dependency for the database session
def get_db_context() -> Session:
    # We may choose to use the CallbackContext to get the database session
    # For now, though, we expect only one database
    return next(get_db())

#
async def send_typing(update: Update, context: CallbackContext) -> None:
    # Send that the bot is typing so the user knows to wait
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
