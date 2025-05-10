import json
import os
import time
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from workers.rag_processor.jobs.twitter_job import process_twitter_data
from workers.rag_processor.jobs.telegram_job import process_telegram_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RAGProcessorScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.last_run_file = Path(__file__).parent / "last_run.json"
        self._load_last_run()
        self._setup_signal_handlers()
        self.is_running = False

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()

    def _load_last_run(self):
        """Load last run timestamps from file"""
        if self.last_run_file.exists():
            with open(self.last_run_file, 'r') as f:
                self.last_run = json.load(f)
        else:
            # Initialize with None to process all historical data on first run
            self.last_run = {
                'twitter': None,
                'telegram': None
            }
            self._save_last_run()

    def _save_last_run(self):
        """Save last run timestamps to file"""
        try:
            with open(self.last_run_file, 'w') as f:
                json.dump(self.last_run, f, indent=2)
            logger.debug("Successfully saved last run timestamps")
        except Exception as e:
            logger.error(f"Error saving last run timestamps: {str(e)}")

    def process_all_sources(self):
        """Process data from all sources since last run"""
        if not self.is_running:
            logger.warning("Scheduler is not running, skipping processing")
            return

        current_time = datetime.now().isoformat()
        
        try:
            # Process Twitter data
            twitter_last_run = self.last_run.get('twitter')
            logger.info(f"Processing Twitter data since {twitter_last_run}")
            new_twitter_data = process_twitter_data(twitter_last_run)
            self.last_run['twitter'] = current_time
            if new_twitter_data:
                logger.info("Successfully processed new Twitter data")
            else:
                logger.info("No new Twitter data to process")

            # Process Telegram data
            telegram_last_run = self.last_run.get('telegram')
            logger.info(f"Processing Telegram data since {telegram_last_run}")
            new_telegram_data = process_telegram_data(telegram_last_run)
            self.last_run['telegram'] = current_time
            if new_telegram_data:
                logger.info("Successfully processed new Telegram data")
            else:
                logger.info("No new Telegram data to process")

            # Save last run timestamps
            self._save_last_run()
            logger.info("Updated last run timestamps")

        except Exception as e:
            logger.error(f"Error processing data: {str(e)}", exc_info=True)
            # Still update last run to avoid reprocessing the same data
            self.last_run['twitter'] = current_time
            self.last_run['telegram'] = current_time
            self._save_last_run()

    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Run immediately on startup to process any missed data
            self.is_running = True
            self.process_all_sources()
            
            # Schedule regular runs
            self.scheduler.add_job(
                self.process_all_sources,
                trigger=IntervalTrigger(minutes=5),
                id='process_rag_data',
                replace_existing=True
            )
            self.scheduler.start()
            logger.info("RAG Processor Scheduler started")
        except Exception as e:
            self.is_running = False
            logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)
            raise

    def stop(self):
        """Stop the scheduler gracefully"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            logger.info("Initiating graceful shutdown...")
            self.is_running = False
            
            # Save current state
            self._save_last_run()
            
            # Shutdown scheduler
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("Scheduler shutdown complete")
            
            logger.info("Graceful shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        finally:
            # Ensure we exit cleanly
            sys.exit(0)

if __name__ == "__main__":
    scheduler = RAGProcessorScheduler()
    try:
        scheduler.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        scheduler.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        scheduler.stop() 