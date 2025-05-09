# utils/permissions.py

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
import logging

logger = logging.getLogger(__name__)

async def check_group_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if bot has necessary permissions in group"""
    try:
        bot = await context.bot.get_me()
        chat = update.effective_chat
        bot_member = await chat.get_member(bot.id)
        
        # Log bot member status and permissions
        logger.info(f"Bot member status: {bot_member.status}")
        logger.info(f"Bot member permissions: {bot_member.privileges if hasattr(bot_member, 'privileges') else 'No privileges'}")
        
        # Check if bot is admin
        if bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            # Admin has all permissions by default
            logger.info("Bot is admin, has all permissions")
            return True
            
        # For regular members, check specific permissions
        missing_permissions = []
        
        # Regular members can always read messages
        # Only check if they can send messages
        if not getattr(bot_member, "can_send_messages", True):
            missing_permissions.append("send messages")
            
        if missing_permissions:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"⚠️ I need permission to {', '.join(missing_permissions)} to help you. Please grant me the necessary permissions.",
                parse_mode="Markdown"
            )
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return False 