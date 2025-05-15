import aiohttp
import logging
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

ALERT_URL = os.getenv('ALERT_URL', 'http://45.32.111.45:5000/alert')
AIRDROP_URL = os.getenv('AIRDROP_URL', 'http://45.32.111.45:5000/alert_airdrop')
SOCIAL_URL = os.getenv('SOCIAL_URL', 'http://45.32.111.45:5000/summary_social')

logger.info(f"Alert URL: {ALERT_URL}")
logger.info(f"Airdrop URL: {AIRDROP_URL}")
logger.info(f"Social URL: {SOCIAL_URL}")
schedule_interval = int(os.getenv('SCHEDULE_DATA_INTERVAL', "4"))

async def fetch_alerts():
    try:
        logger.info("Fetching market alerts from API...")
        async with aiohttp.ClientSession() as session:
            async with session.post(ALERT_URL, json={"time": schedule_interval * 60}) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch market alerts. Status: {resp.status}")
                    return []
                data = await resp.json()
                alerts = data.get('data', [])
                logger.info(f"Successfully fetched {len(alerts)} market alerts")
                return alerts
    except aiohttp.ClientError as e:
        logger.error(f"Network error while fetching market alerts: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error fetching market alerts: {str(e)}")
        return []

async def fetch_airdrop_alerts():
    try:
        logger.info("Fetching airdrop alerts from API...")
        async with aiohttp.ClientSession() as session:
            async with session.post(AIRDROP_URL, json={"time": 15}) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch airdrop alerts. Status: {resp.status}")
                    return []
                data = await resp.json()
                airdrops = data.get('data', [])
                logger.info(f"Successfully fetched {len(airdrops)} airdrop alerts")
                return {
                    'alert_type': 'airdrop',
                    'airdrops': airdrops
                }
    except aiohttp.ClientError as e:
        logger.error(f"Network error while fetching airdrop alerts: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error fetching airdrop alerts: {str(e)}")
        return []

async def fetch_social_sentiment():
    try:
        logger.info("Fetching social media sentiment data from API...")
        async with aiohttp.ClientSession() as session:
            async with session.post(SOCIAL_URL, json={}) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch social sentiment data. Status: {resp.status}")
                    return None
                data = await resp.json()
                if not data.get('success'):
                    logger.error("API returned unsuccessful response")
                    return None
                sentiment_data = data.get('data')
                if sentiment_data and sentiment_data.get('text'):
                    logger.info("Successfully fetched social media sentiment data")
                    return {
                        'alert_type': 'social',
                        'text': sentiment_data['text'],
                        'sentiment': sentiment_data.get('sentiment', 'unknown')
                    }
                logger.warning("No sentiment text found in response")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Network error while fetching social sentiment data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error fetching social sentiment data: {str(e)}")
        return None 