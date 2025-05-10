import json
import os
import time
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from jobs.twitter_job import process_twitter_data
from jobs.telegram_job import process_telegram_data

class RAGProcessorScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.last_run_file = Path(__file__).parent / "last_run.json"
        self._load_last_run()

    def _load_last_run(self):
        if self.last_run_file.exists():
            with open(self.last_run_file, 'r') as f:
                self.last_run = json.load(f)
        else:
            self.last_run = {
                'twitter': None,
                'telegram': None
            }
            self._save_last_run()

    def _save_last_run(self):
        with open(self.last_run_file, 'w') as f:
            json.dump(self.last_run, f, indent=2)

    def process_all_sources(self):
        """Process data from all sources"""
        try:
            # Process Twitter data
            twitter_last_run = self.last_run.get('twitter')
            new_twitter_data = process_twitter_data(twitter_last_run)
            if new_twitter_data:
                self.last_run['twitter'] = datetime.now().isoformat()

            # Process Telegram data
            telegram_last_run = self.last_run.get('telegram')
            new_telegram_data = process_telegram_data(telegram_last_run)
            if new_telegram_data:
                self.last_run['telegram'] = datetime.now().isoformat()

            # Save last run timestamps
            self._save_last_run()

        except Exception as e:
            print(f"Error processing data: {str(e)}")

    def start(self):
        """Start the scheduler"""
        self.scheduler.add_job(
            self.process_all_sources,
            trigger=IntervalTrigger(minutes=5),
            id='process_rag_data',
            replace_existing=True
        )
        self.scheduler.start()

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()

if __name__ == "__main__":
    scheduler = RAGProcessorScheduler()
    scheduler.start()
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop() 