import os
import logging
from collections import defaultdict
from telegram import Bot
from workers.notify_worker.store import get_active_users
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

logger.info("Initializing Telegram bot...")
bot = Bot(token=TELEGRAM_BOT_TOKEN)
logger.info("Telegram bot initialized successfully")

ALERT_TYPE_MAP = {
    'market': '🌐 <b>Market Trends</b>',
    'coin': '💹 <b>Coin Alerts</b>',
    'claim': '✅ <b>Claim Opportunities</b>',
    'rumor': '🤫 <b>Market Rumors</b>',
    'social': '📊 <b>Market Sentiment Analysis</b>',
    'airdrop': '💰 <b>Airdrop Detected</b>'
}

def format_message(alerts, airdrops):
    try:
        logger.info(f"Formatting message for {len(alerts)} alerts and {len(airdrops)} airdrops")
        grouped = defaultdict(list)
        for alert in alerts + airdrops:
            key = alert.get('alert_type') or 'other'
            grouped[key].append(alert)
        
        parts = []
        for k, v in grouped.items():
            title = ALERT_TYPE_MAP.get(k, f'📌 <b>{k.capitalize()}</b>')
            section = [title]
            logger.info(f"Processing {k} alerts: {v}")
            for item in v:
                if k == 'social':
                    # For social sentiment, just use the text directly
                    section.append(item.get('text', ''))
                elif k == 'airdrop':
                    section.append(f"• {item.get('text', '')}")
                else:
                    text = item.get('text', '')
                    # post_link = item.get('post_link', '')
                    # if post_link:
                    #     section.append(f'<a href="{post_link}">View</a>')
                    # else:
                    section.append(text)
            parts.append('\n'.join(section))
        
        message = '\n\n'.join(parts)
        logger.info("Message formatted successfully")
        return message
    except Exception as e:
        logger.error(f"Error formatting message: {str(e)}")
        raise

async def notify_users(alerts, airdrops):
    try:
        logger.info("Starting notification process...")
        message = format_message(alerts, airdrops)
        if not message.strip():
            logger.info("No message to send, skipping notifications")
            return
            
        user_ids = await get_active_users()
        logger.info(f"Found {len(user_ids)} active users to notify")
        
        success_count = 0
        error_count = 0
        
        for user_id in user_ids:
            try:
                logger.info(f"Sending notification to user {user_id}")
                await bot.send_message(chat_id=int(user_id), text=message, parse_mode='HTML')
                success_count += 1
                logger.info(f"Successfully sent notification to user {user_id}")
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to send notification to user {user_id}: {str(e)}")
                
        logger.info(f"Notification process completed. Success: {success_count}, Errors: {error_count}")
    except Exception as e:
        logger.error(f"Error in notify_users: {str(e)}")
        raise 