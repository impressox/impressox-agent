# handlers/message_handler.py

from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from clients.session_manager import get_session_id, reset_session_id
from clients.telegram.services.core_api import send_message_to_core
from clients.telegram.utils.permissions import check_group_permissions
from clients.telegram.services.chat_history import get_chat_history_service
from clients.telegram.utils.logger import logger
import asyncio

def extract_ai_response(api_result):
    """
    Extract content của message AI cuối cùng từ dict trả về của API.
    """
    logger.debug(f"Extracting AI response from: {api_result}")
    
    if not api_result:
        logger.error("Empty API result received")
        return "Sorry, I couldn't process your request. Please try again."
        
    if isinstance(api_result, dict):
        # Check for error in response
        if "error" in api_result:
            logger.error(f"API returned error: {api_result['error']}")
            return f"Sorry, an error occurred: {api_result['error']}"
            
        # Get messages from result field
        result = api_result.get("result", {})
        messages = result.get("messages", [])
        
        if not messages:
            logger.warning("No messages found in API response")
            return "Sorry, I couldn't generate a response. Please try again."
            
        # Look for AI message in reverse order
        for msg in reversed(messages):
            if msg.get("type") == "ai":
                content = msg.get("content", "")
                if content:
                    logger.debug(f"Found AI response: {content[:100]}...")
                    return content
                    
        logger.warning("No AI message found in response")
        return "Sorry, I couldn't generate a proper response. Please try again."
        
    logger.error(f"Unexpected API result type: {type(api_result)}")
    return "Sorry, I received an unexpected response format. Please try again."

async def keep_typing(chat_id: int, bot: Bot, stop_event: asyncio.Event):
    """Keep sending typing action until stop_event is set"""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)  # Send typing action every 4 seconds
        except Exception as e:
            logger.error(f"Error sending typing action: {e}")
            break

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    try:
        # Check if update has message
        if not update.message:
            logger.warning("Received update without message")
            return

        # Get message text
        user_message = update.message.text
        if not user_message:
            logger.warning("Received message without text")
            return

        # Get chat info
        chat = update.message.chat
        chat_id = chat.id
        chat_type = chat.type
        user = update.message.from_user
        user_id = user.id if user else None
        username = user.username if user else None

        logger.info(f"Received message from {username} ({user_id}) in {chat_type} {chat_id}: {user_message}")

        # Start typing action in background
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(chat_id, context.bot, stop_typing))

        try:
            session_id = get_session_id(user_id, platform="telegram")

            # Check bot permissions in groups
            if chat_type != "private":
                # Check permissions and get bot info
                if not await check_group_permissions(update, context):
                    return
                
                # Get bot info
                bot = await context.bot.get_me()
                
                # Check if message is a reply to bot's message
                is_reply_to_bot = False
                if update.message.reply_to_message:
                    reply_to_message = update.message.reply_to_message
                    if reply_to_message.from_user and reply_to_message.from_user.id == bot.id:
                        is_reply_to_bot = True
                
                # Check if message contains bot's username or is reply to bot's message
                if not is_reply_to_bot and f"@{bot.username}" not in user_message:
                    return  # Ignore messages that don't tag the bot or reply to bot's message
                
                # Remove bot's username from message if present
                if f"@{bot.username}" in user_message:
                    user_message = user_message.replace(f"@{bot.username}", "").strip()
                
                # If message is empty after removing username, ignore it
                if not user_message:
                    return

            # Get user info
            user = update.effective_user
            chat = update.effective_chat

            configurable_dict = {
                # Original fields
                "app": "telegram",
                "user_id": str(user.id),
                "conversation_id": chat.id,
                "user_name": user.username,
                "user_full_name": user.full_name,
                "gender": "unknown",
                "x_birthdate": "unknown",
                "response_markdown": True,
                "message_id": str(update.message.message_id),
                "version": 4,
                "language": getattr(user, "language_code", "en"),
                "chat_type": chat.type,
                "chat_title": getattr(chat, "title", None),
                
                # Additional user info
                "user_language": getattr(user, "language_code", "en"),
                "user_is_bot": user.is_bot,
                "user_is_premium": getattr(user, "is_premium", False),
                
                # Additional chat info
                "chat_id": str(chat.id),
                "chat_username": getattr(chat, "username", None),
                "chat_is_forum": getattr(chat, "is_forum", False),
                
                # Additional message info
                "message_date": update.message.date.isoformat(),
                "message_thread_id": getattr(update.message, "message_thread_id", None),
                "is_reply": bool(update.message.reply_to_message),
                "reply_to_message_id": str(update.message.reply_to_message.message_id) if update.message.reply_to_message else None,
                "reply_to_user_id": str(update.message.reply_to_message.from_user.id) if update.message.reply_to_message and update.message.reply_to_message.from_user else None,
            }
            
            logger.debug(f"Configurable dict: {configurable_dict}")

            # First attempt with current session
            api_result = await send_message_to_core(session_id, user_message, configurable_dict)
            logger.debug(f"Raw API result: {api_result}")
            
            ai_response = extract_ai_response(api_result)
            logger.debug(f"Extracted AI response: {ai_response[:100]}...")

            # If response indicates session error, reset session and retry once
            if "Would you like me to restart the conversation for you?" in ai_response:
                logger.warning(f"Session error detected for user {user_id}, resetting session and retrying...")
                new_session_id = reset_session_id(user_id, platform="telegram")
                api_result = await send_message_to_core(new_session_id, user_message, configurable_dict)
                logger.debug(f"Retry API result: {api_result}")
                ai_response = extract_ai_response(api_result)
                logger.debug(f"Retry extracted AI response: {ai_response[:100]}...")

            # Save chat history
            chat_history_service = await get_chat_history_service()
            
            # Save user message
            await chat_history_service.save_message(
                message=user_message,
                user_id=str(user.id),
                chat_id=str(chat.id),
                chat_type=chat.type,
                metadata={
                    "message_type": "user",
                    "user_name": user.username,
                    "user_full_name": user.full_name,
                    "message_id": str(update.message.message_id),
                    "thread_id": getattr(update.message, "message_thread_id", None),
                    "is_reply": bool(update.message.reply_to_message),
                    "reply_to_message_id": str(update.message.reply_to_message.message_id) if update.message.reply_to_message else None,
                    "reply_to_user_id": str(update.message.reply_to_message.from_user.id) if update.message.reply_to_message and update.message.reply_to_message.from_user else None,
                }
            )
            
            # Save AI response
            await chat_history_service.save_message(
                message=ai_response,
                user_id="ai",
                chat_id=str(chat.id),
                chat_type=chat.type,
                metadata={
                    "message_type": "ai",
                    "session_id": session_id,
                    "message_id": str(update.message.message_id),
                    "thread_id": getattr(update.message, "message_thread_id", None)
                }
            )

            # Send response to chat
            try:
                await update.message.reply_text(ai_response, parse_mode="Markdown", disable_web_page_preview=True)
                logger.info("Successfully sent response to chat")
            except Exception as e:
                logger.error(f"Error sending response to chat: {e}")
                # Try sending without markdown if markdown parsing fails
                try:
                    await update.message.reply_text(ai_response, disable_web_page_preview=True)
                    logger.info("Successfully sent response without markdown")
                except Exception as e2:
                    logger.error(f"Error sending response without markdown: {e2}")
                    await update.message.reply_text("Sorry, I couldn't send my response properly. Please try again.")
        finally:
            # Stop typing action
            stop_typing.set()
            await typing_task
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        try:
            await update.message.reply_text("Sorry, an error occurred while processing your message. Please try again.")
        except:
            pass

async def handle_new_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new command"""
    try:
        user_id = update.effective_user.id
        new_session_id = reset_session_id(user_id, platform="telegram")
        await update.message.reply_text("""
*🔄 New conversation started!*

Lili's here to help with DeFi, tokens, swaps, wallets & more.
Ask me anything — let's dive into Web3 🚀
""", parse_mode="Markdown")
    except TelegramError as e:
        logger.error(f"Telegram error in handle_new_session: {e}")

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user_id = update.effective_user.id
        new_session_id = reset_session_id(user_id, platform="telegram")
        
        # Get bot info
        bot = await context.bot.get_me()
        
        # Different welcome message for groups
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                f"""
*👋 Hi, I'm Lili — your crypto AI assistant from CpX!*

I can help with DeFi, NFTs, wallets, and more.

To chat with me in this group:
1. Mention me using `@{bot.username}`
2. Type your question

For private chat, just DM me directly!

Type `/new` to start a fresh conversation.
""", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                """
*👋 Hi, I'm Lili — your crypto AI assistant from CpX.*

I can help you:

Explain DeFi, NFTs, wallets, and on-chain trends

Track wallet activity and detect suspicious tokens

Analyze your portfolio and suggest strategies

Simulate and assist with token swaps

🆕 Type `/new` anytime to start a fresh conversation.
Let's explore the Web3 world together!
""", parse_mode="Markdown")
    except TelegramError as e:
        logger.error(f"Telegram error in handle_start: {e}")

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when bot is added to or removed from groups"""
    try:
        bot = await context.bot.get_me()
        chat = update.effective_chat
        new_status = update.new_chat_member.status
        old_status = update.old_chat_member.status

        # Bot was added to a group
        if new_status == ChatMemberStatus.MEMBER and old_status != ChatMemberStatus.MEMBER:
            # Check if bot has necessary permissions
            bot_member = await chat.get_member(bot.id)
            missing_permissions = []
            if not bot_member.can_send_messages:
                missing_permissions.append("send messages")
            if not bot_member.can_read_messages:
                missing_permissions.append("read messages")
            
            if missing_permissions:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"⚠️ I need permission to {', '.join(missing_permissions)} to help you. Please grant me the necessary permissions.",
                    parse_mode="Markdown"
                )
                return

            # Send welcome message
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"""
*👋 Hi everyone! I'm Lili — your crypto AI assistant from CpX!*

I can help with DeFi, NFTs, wallets, and more.

To chat with me in this group:
1. Mention me using `@{bot.username}`
2. Type your question

For private chat, just DM me directly!

Type `/new` to start a fresh conversation.
""",
                parse_mode="Markdown"
            )

        # Bot was removed from a group
        elif new_status != ChatMemberStatus.MEMBER and old_status == ChatMemberStatus.MEMBER:
            # Clean up any group-specific data if needed
            pass
    except TelegramError as e:
        logger.error(f"Telegram error in handle_chat_member_update: {e}")