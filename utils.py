import logging

def error_handler(update, context):
    logging.error(f"Update {update} caused error {context.error}")

