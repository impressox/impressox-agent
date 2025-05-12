# handlers/message_handler.py

from telegram import Update, Bot, ChatMemberRestricted, ChatMemberAdministrator
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from clients.session_manager import get_session_id, reset_session_id
from clients.telegram.services.core_api import send_message_to_core
from clients.telegram.utils.permissions import check_group_permissions
from clients.telegram.services.chat_history import get_chat_history_service
from clients.telegram.utils.logger import logger
from clients.telegram.utils.redis_util import publish_notify_on, publish_notify_off
import asyncio

def extract_ai_response(api_result):
    """
    Extract content của message AI cuối cùng từ dict trả về của API.
    """
    logger.debug(f"Extracting AI response from: {api_result}")
    
    if not api_result:
        logger.error("Empty API result received")
        return "I apologize, but I couldn't process your request. Please try again in a moment."
        
    if isinstance(api_result, dict):
        # Check for error in response
        if "error" in api_result:
            logger.error(f"API returned error: {api_result['error']}")
            return api_result['error']  # Use the friendly error message we set in core_api.py
            
        # Get messages from result field
        result = api_result.get("result", {})
        messages = result.get("messages", [])
        
        if not messages:
            logger.warning("No messages found in API response")
            return "I apologize, but I couldn't generate a response. Please try again in a moment."
            
        # Look for AI message in reverse order
        for msg in reversed(messages):
            if msg.get("type") == "ai":
                content = msg.get("content", "")
                if content:
                    logger.debug(f"Found AI response: {content[:100]}...")
                    return content
                    
        logger.warning("No AI message found in response")
        return "I apologize, but I couldn't generate a proper response. Please try again in a moment."
        
    logger.error(f"Unexpected API result type: {type(api_result)}")
    return "I apologize, but I received an unexpected response format. Please try again in a moment."

async def keep_typing(chat_id: int, bot: Bot, stop_event: asyncio.Event):
    """Keep sending typing action until stop_event is set"""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(2)  # Send typing action every 4 seconds
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

        # Save all messages to chat history
        try:
            chat_history_service = await get_chat_history_service()
            
            # Get replied message content if exists
            replied_message_content = None
            if update.message.reply_to_message:
                reply_to_message = update.message.reply_to_message
                if reply_to_message.text:  # Only get content if there is text
                    replied_message_content = reply_to_message.text

            # Save the message to chat history
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
                    "replied_message_content": replied_message_content
                }
            )
        except Exception as e:
            logger.error(f"Error saving message to chat history: {e}")
            # Continue with message processing even if saving fails

        # Check if this is a message for the bot
        is_bot_message = False
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
            
            is_bot_message = True
        else:
            is_bot_message = True

        # If this is a message for the bot, process it
        if is_bot_message:
            # Start typing action in background
            stop_typing = asyncio.Event()
            typing_task = asyncio.create_task(keep_typing(chat_id, context.bot, stop_typing))

            try:
                # For group chats, use chat_id as session key
                # For private chats, use user_id as session key
                session_key = str(chat_id) if chat_type != "private" else str(user_id)
                session_id = get_session_id(platform="telegram", session_key=session_key)

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
                    "replied_message_content": replied_message_content,
                }
                
                logger.debug(f"Configurable dict: {configurable_dict}")

                # First attempt with current session
                api_result = await send_message_to_core(session_id, user_message, configurable_dict)
                logger.debug(f"Raw API result: {api_result}")
                
                ai_response = extract_ai_response(api_result)
                logger.debug(f"Extracted AI response: {ai_response[:100]}...")

                # If response indicates session error, reset session and retry once
                if "Would you like me to restart the conversation for you?" in ai_response:
                    logger.warning(f"Session error detected for {'group' if chat_type != 'private' else 'user'} {chat_id if chat_type != 'private' else user_id}, resetting session and retrying...")
                    new_session_id = reset_session_id(platform="telegram", session_key=session_key)
                    api_result = await send_message_to_core(new_session_id, user_message, configurable_dict)
                    logger.debug(f"Retry API result: {api_result}")
                    ai_response = extract_ai_response(api_result)
                    logger.debug(f"Retry extracted AI response: {ai_response[:100]}...")

                # Save AI response to chat history
                try:
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
                except Exception as e:
                    logger.error(f"Error saving AI response to chat history: {e}")
                    # Continue with sending response even if saving fails

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
                        await update.message.reply_text(
                            "I apologize, but I'm having trouble sending my response. Please try again in a moment.",
                            parse_mode="Markdown"
                        )
            finally:
                # Stop typing action
                stop_typing.set()
                await typing_task

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "I apologize, but I encountered an unexpected error. Please try again in a moment.",
                parse_mode="Markdown"
            )
        except:
            pass

async def handle_new_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new command"""
    try:
        user_id = update.effective_user.id
        chat = update.effective_chat
        # For group chats, use chat_id as session key
        # For private chats, use user_id as session key
        session_key = str(chat.id) if chat.type != "private" else str(user_id)
        new_session_id = reset_session_id(platform="telegram", session_key=session_key)

        # New session message
        new_session_message = """*🔄 New conversation started!*

Lili's here to help with DeFi, tokens, swaps, wallets & more.
Ask me anything — let's dive into Web3 🚀"""

        # Start typing action
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(chat.id, context.bot, stop_typing))

        try:
            # Calculate typing delay based on message length (roughly 50 chars per second)
            typing_delay = min(len(new_session_message) / 50, 2)  # Cap at 2 seconds
            await asyncio.sleep(typing_delay)
            
            await update.message.reply_text(
                text=new_session_message,
                parse_mode="Markdown"
            )
        finally:
            # Stop typing action
            stop_typing.set()
            await typing_task

    except TelegramError as e:
        logger.error(f"Telegram error in handle_new_session: {e}")
        try:
            await update.message.reply_text(
                "I apologize, but I couldn't start a new conversation. Please try again in a moment.",
                parse_mode="Markdown"
            )
        except:
            pass

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user_id = update.effective_user.id
        chat = update.effective_chat
        # For group chats, use chat_id as session key
        # For private chats, use user_id as session key
        session_key = str(chat.id) if chat.type != "private" else str(user_id)
        new_session_id = reset_session_id(platform="telegram", session_key=session_key)
        
        # Get bot info
        bot = await context.bot.get_me()
        
        # Different welcome messages for groups vs private chat
        if update.effective_chat.type != "private":
            # Group welcome messages
            welcome_messages = [
                "Hi there, this is *Lili*. Thank you for inviting me to the group.",
                
                "I am an *AI agent* providing *real-time notifications* about the latest news, insights, and *AI/ML-powered predictions* on the cryptocurrency and NFT markets.",
                
                f"""*To chat with me in this group:*  
1. Mention me using `@{bot.username}`  
2. Type your question  
3. Use `/new` to start a fresh conversation  

For private chat, just send me a direct message!""",
                
                "*Would you like to try real-time market notifications?*"
            ]
        else:
            # Enable notifications automatically for private chat
            publish_notify_on(str(user_id), "private")
            
            # Private chat welcome messages
            welcome_messages = [
                "Hi there, this is *Lili*. I am an *AI agent* that will notify you on the *REAL TIME* basis about the latest news, insights and *AI/ML basing predictions* on the cryptocurrency and NFT market",
                
                "Yet you can also ask me anything that you need about the markets. I'm here to assist your investment.",
                
                "🆕 Type `/new` anytime to start a fresh conversation.",
                
                "✅ I've automatically enabled market notifications for you\\. You'll receive updates about:\n• Market trends and analysis\n• Coin alerts and opportunities\n• Social media sentiment\n\n"
                "Use `/notify_off` to stop receiving notifications\\."
            ]

        # Add a small delay before starting welcome messages
        for message in welcome_messages:
            try:
                # Start typing action for this message
                stop_typing = asyncio.Event()
                typing_task = asyncio.create_task(keep_typing(chat.id, context.bot, stop_typing))

                try:
                    # Calculate typing delay based on message length (roughly 50 chars per second)
                    typing_delay = min(len(message) / 50, 0.5)  # Cap at 2 seconds
                    await asyncio.sleep(typing_delay)
                    
                    await update.message.reply_text(
                        text=message,
                        parse_mode="Markdown"
                    )
                finally:
                    # Stop typing action
                    stop_typing.set()
                    await typing_task
            except Exception as e:
                logger.error(f"Error sending welcome message: {e}")
                # Continue with next message even if one fails

    except TelegramError as e:
        logger.error(f"Telegram error in handle_start: {e}")
        try:
            await update.message.reply_text(
                "I apologize, but I couldn't start our conversation properly. Please try again in a moment.",
                parse_mode="Markdown"
            )
        except:
            pass

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when bot is added to or removed from groups"""
    try:
        logger.info(f"Chat member update (my_chat_member): {update}")
        bot = await context.bot.get_me()
        member = update.my_chat_member
        chat = member.chat
        new_status = member.new_chat_member.status
        old_status = member.old_chat_member.status

        # Bot was added to a group
        if new_status == ChatMemberStatus.MEMBER and old_status != ChatMemberStatus.MEMBER:
            # Check if bot has necessary permissions
            bot_member = await chat.get_member(bot.id)
            missing_permissions = []
            # Nếu là Admin, skip kiểm tra
            if isinstance(bot_member, ChatMemberAdministrator):
                pass
            elif isinstance(bot_member, ChatMemberRestricted):
                if not bot_member.can_send_messages:
                    missing_permissions.append("send messages")
                if not bot_member.can_read_all_group_messages:
                    missing_permissions.append("read all messages")
            else:
                # Nếu là thành viên bình thường → không biết quyền rõ ràng → khuyến cáo
                missing_permissions.append("send and read messages")

            # Send welcome messages
            welcome_messages = [
                "Hi there, this is *Lili*. Thank you for inviting me to the group.",

                "I am an *AI agent* providing *real-time notifications* about the latest news, insights, and *AI/ML-powered predictions* on the cryptocurrency and NFT markets.",

                f"""*To chat with me in this group:*  
1. Mention me using `@{bot.username}`  
2. Type your question  
3. Use `/new` to start a fresh conversation  

For private chat, just send me a direct message!""",

                "✅ I've automatically enabled market notifications for this group. You'll receive updates about:\n• Market trends and analysis\n• Coin alerts and opportunities\n• Social media sentiment\n\nUse `/notify_off` to stop receiving notifications.",
                missing_permissions and len(missing_permissions) > 0 and f"⚠️ I need permission to *{', '.join(missing_permissions)}* to help you. Please grant me the necessary permissions."
            ]

            for message in welcome_messages:
                try:
                    if not message or not isinstance(message, str):
                        continue
                    stop_typing = asyncio.Event()
                    typing_task = asyncio.create_task(keep_typing(chat.id, context.bot, stop_typing))

                    typing_delay = min(len(message) / 50, 0.5)
                    await asyncio.sleep(typing_delay)

                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=message,
                        parse_mode="Markdown"
                    )
                finally:
                    stop_typing.set()
                    await typing_task
            
            # Enable notifications for the group
            publish_notify_on(str(chat.id), "group")
        # Bot was removed from group
        elif old_status == ChatMemberStatus.MEMBER and new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            publish_notify_off(str(chat.id), "group")
            # Clean up any group-specific data if needed
            logger.info(f"Bot was removed from group: {chat.id}")
            # Optionally: remove chat.id from notification list
            pass

    except TelegramError as e:
        logger.error(f"Telegram error in handle_chat_member_update: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id if update.effective_chat else None,
                text="I encountered an error while setting up. Please try adding me again.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def handle_notify_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /notify_on command"""
    try:
        chat = update.effective_chat
        chat_type = chat.type
        
        # Use chat_id for groups, user_id for private chats
        target_id = str(chat.id) if chat_type != "private" else str(update.effective_user.id)
        
        # Publish notification on message
        publish_notify_on(target_id, chat_type)
        
        await update.message.reply_text(
            "✅ You will now receive market notifications\\.\n\n"
            "You'll get updates about:\n"
            "• Market trends and analysis\n"
            "• Coin alerts and opportunities\n"
            "• Social media sentiment\n\n"
            "Use `/notify_off` to stop receiving notifications\\.",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_notify_on: {e}")
        try:
            await update.message.reply_text(
                "I apologize, but I couldn't enable notifications\\. Please try again in a moment\\.",
                parse_mode="MarkdownV2"
            )
        except:
            pass

async def handle_notify_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /notify_off command"""
    try:
        chat = update.effective_chat
        chat_type = chat.type
        
        # Use chat_id for groups, user_id for private chats
        target_id = str(chat.id) if chat_type != "private" else str(update.effective_user.id)
        
        # Publish notification off message
        publish_notify_off(target_id, chat_type)
        
        await update.message.reply_text(
            "🔕 You will no longer receive market notifications.\n\n"
            "Use `/notify_on` to start receiving notifications again.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_notify_off: {e}")
        try:
            await update.message.reply_text(
                "I apologize, but I couldn't disable notifications. Please try again in a moment.",
                parse_mode="Markdown"
            )
        except:
            pass