# bot.py

from telegram.ext import Application, MessageHandler, filters, CommandHandler, ChatMemberHandler, ContextTypes
from telegram import Update, BotCommand
from telegram.constants import ChatMemberStatus
from clients.config import TELEGRAM_BOT_TOKEN
from clients.telegram.handlers.message_handler import (
    handle_message, 
    handle_new_session, 
    handle_start,
    handle_chat_member_update
)
from clients.telegram.utils.logger import logger

# Singleton instance
_bot_application = None

async def setup_commands(application: Application):
    """Setup bot commands"""
    commands = [
        BotCommand("start", "Show basic instructions and start a new conversation with Lili"),
        BotCommand("new", "Start a fresh conversation with Lili"),
        BotCommand("help", "Show help message")
    ]
    await application.bot.set_my_commands(commands)

def get_bot_application() -> Application:
    """Get or create the bot application instance"""
    global _bot_application
    if _bot_application is None:
        _bot_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Register handlers
        # Handle private messages
        private_message_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND) & filters.ChatType.PRIVATE,
            handle_message
        )
        _bot_application.add_handler(private_message_handler)

        # Handle group messages (when bot is mentioned)
        group_message_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND) & filters.ChatType.GROUPS & filters.Entity("mention"),
            handle_message
        )
        _bot_application.add_handler(group_message_handler)

        # Handle reply messages in groups (when user replies to bot's message)
        group_reply_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND) & filters.ChatType.GROUPS & filters.REPLY,
            handle_message
        )
        _bot_application.add_handler(group_reply_handler)

        # Handle commands
        _bot_application.add_handler(CommandHandler("new", handle_new_session))
        _bot_application.add_handler(CommandHandler("start", handle_start))
        _bot_application.add_handler(CommandHandler("help", handle_start))

        # Handle chat member updates (when bot is added/removed from groups)
        _bot_application.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    return _bot_application

def main():
    """Main entry point"""
    application = get_bot_application()
    logger.info("Telegram AI client is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
