import json
import logging
import asyncio
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoClient
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.api import call_api
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)

class AirdropWatcher(BaseWatcher):
    """Worker để theo dõi thông tin airdrop từ các dự án"""
    
    def __init__(self):
        super().__init__()
        self.watch_type = "airdrop"
        self.config = get_config()
        self._stop_event = asyncio.Event()
        self.airdrop_cache = {}  # Cache airdrop data to detect changes
        self.watch_interval = int(os.getenv("AIRDROP_WATCH_INTERVAL", "900"))  # Check more frequently for wallets
        
    def _serialize_to_json(self, data):
        """Helper method to serialize data to JSON string"""
        return json.dumps(data, cls=MongoJSONEncoder)

    def _deserialize_from_json(self, json_str):
        """Helper method to deserialize JSON string to dict"""
        if isinstance(json_str, dict):
            return json_str
        if isinstance(json_str, bytes):
            json_str = json_str.decode('utf-8')
        return json.loads(json_str)
            
    async def initialize(self):
        """Khởi tạo kết nối Redis và MongoDB"""
        try:
            await self.start()  # Use base class start method
            logger.info("[AirdropWatcher] Initialized successfully")
        except Exception as e:
            logger.error(f"[AirdropWatcher] Error initializing: {e}")
            raise
            
    async def stop(self):
        """Dừng worker"""
        try:
            logger.info("[AirdropWatcher] Stopping...")
            self._stop_event.set()
            await super().stop()  # Use base class stop method
            logger.info("[AirdropWatcher] Stopped successfully")
        except Exception as e:
            logger.error(f"[AirdropWatcher] Error stopping: {e}")
            
    async def watch_targets(self):
        """Watch airdrop targets and check conditions"""
        try:
            # Get airdrop data
            logger.info(f"[AirdropWatcher] Checking airdrops for targets: {list(self.watching_targets)}")
            
            # Get target_data from active rules
            target_data = {}
            for target in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:airdrop:{target}")
                    if not rules:
                        logger.warning(f"[AirdropWatcher] No rules found for target {target}")
                        continue
                        
                    for rule_id, rule_json in rules.items():
                        try:
                            rule_dict = self._deserialize_from_json(rule_json)
                            logger.debug(f"[AirdropWatcher] Deserialized rule for target {target}: {rule_dict}")
                            rule = Rule.from_dict(rule_dict)
                            if rule.target_data:
                                target_data.update(rule.target_data)
                            break  # Only need data from one rule
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.error(f"[AirdropWatcher] Error decoding rule JSON for target {target}, rule {rule_id}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[AirdropWatcher] Error getting rules for target {target}: {e}")
                    continue

            # Get airdrop data from API
            airdrop_data = await self.get_airdrop_data(list(self.watching_targets))
            if not airdrop_data:
                logger.warning("[AirdropWatcher] No airdrop data received from API")
                return

            logger.info(f"[AirdropWatcher] Received airdrop data: {self._serialize_to_json(airdrop_data)}")

            # Get all active airdrop rules
            active_rules = []
            for target in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:airdrop:{target}")
                    if not rules:
                        continue
                        
                    logger.info(f"[AirdropWatcher] Found {len(rules)} active rules for {target}")
                    for rule_id, rule_json in rules.items():
                        try:
                            rule_dict = self._deserialize_from_json(rule_json)
                            logger.debug(f"[AirdropWatcher] Deserialized rule for target {target}: {rule_dict}")
                            rule = Rule.from_dict(rule_dict)
                            active_rules.append(rule)
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.error(f"[AirdropWatcher] Error decoding rule JSON for target {target}, rule {rule_id}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[AirdropWatcher] Error getting rules for target {target}: {e}")
                    continue

            # Check conditions for each rule
            if active_rules:
                logger.info(f"[AirdropWatcher] Checking {len(active_rules)} rules against airdrop data")
                await self.check_rules(active_rules, airdrop_data)
            else:
                logger.warning("[AirdropWatcher] No active rules found for watching airdrops")

        except Exception as e:
            logger.error(f"[AirdropWatcher] Error watching airdrops: {e}", exc_info=True)

    async def get_airdrop_data(self, targets: List[str]) -> Dict:
        """Get current airdrop data from API"""
        try:
            # Get alert data first
            alert_url = self.config.get_airdrop_alert_url()
            alert_data = {
                "crypto": list(self.watching_targets) if self.watching_targets and '*' not in self.watching_targets else [],
                "time": int(os.getenv("AIRDROP_ALERT_TIME", "15"))
            }
            
            logger.info(f"[AirdropWatcher] Calling alert API: {alert_url}, {alert_data}")
            alert_response = await call_api(
                alert_url,
                method="POST",
                data=alert_data,
                timeout=self.config.get_airdrop_alert_timeout()
            )
            
            # Initialize result with empty data for each target
            result = {target: {"data": {}, "last_updated": datetime.utcnow().isoformat()} for target in targets}
            
            # Process alert response
            alert_matches = []
            if alert_response and alert_response.get("success", False):
                logger.info(f"[AirdropWatcher] Alert API call successful: {alert_response}")
                # Get alerts from nested data structure
                alert_data = alert_response.get("data", {}).get("data", [])
                logger.info(f"[AirdropWatcher] Alert messages: {alert_data}")
                
                # Process each alert message
                for alert in alert_data:
                    if isinstance(alert, dict) and "text" in alert:
                        alert_matches.append({
                            "condition": "alert",
                            "message": alert["text"],
                            "data": {
                                "post_link": alert.get("post_link"),
                                "text": alert["text"]
                            }
                        })
                        logger.info(f"[AirdropWatcher] Added alert match: {alert['text']}")
                logger.info(f"[AirdropWatcher] Found {len(alert_matches)} alert matches")

            # Add alert matches to result
            if alert_matches:
                result["alert_matches"] = alert_matches
                logger.info(f"[AirdropWatcher] Added {len(alert_matches)} alert matches to result")
            
            logger.info(f"[AirdropWatcher] Final result: {self._serialize_to_json(result)}")
            return result
            
        except Exception as e:
            logger.error(f"[AirdropWatcher] Error fetching airdrop data: {e}", exc_info=True)
            return {}

    def evaluate_conditions(self, rule: Rule, airdrop_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against airdrop data"""
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[AirdropWatcher] Evaluating conditions for rule {rule.rule_id}: {self._serialize_to_json(condition)}")

        # Get alert matches from data
        alert_matches = airdrop_data.get("alert_matches", [])

        # Check alert matches
        for alert in alert_matches:
            # The alert structure from get_airdrop_data has:
            # - condition: "alert"
            # - message: alert text
            # - data: original alert data
            alert_data = alert.get("data", {})
            
            # Check if this alert is for any of our target tokens
            is_target_alert = False
            for target in rule.target:
                # For wildcard target (*), match all alerts
                if target == "*":
                    is_target_alert = True
                    logger.info(f"[AirdropWatcher] Wildcard target match found for alert: {alert['message']}")
                    matches.append({
                        "target": alert_data.get("target", "Unknown"),  # Use target from alert data
                        "condition": "alert",
                        "message": alert["message"],
                        "data": alert_data
                    })
                    break
                # For specific targets, check if target is mentioned in the alert message
                elif target.lower() in alert["message"].lower():
                    is_target_alert = True
                    logger.info(f"[AirdropWatcher] Alert match found for target {target}: {alert['message']}")
                    matches.append({
                        "target": target,
                        "condition": "alert",
                        "message": alert["message"],
                        "data": alert_data
                    })
                    break
            
            if not is_target_alert:
                continue

            # If rule has specific alert conditions, check them
            if "alert" in condition:
                alert_condition = condition["alert"]
                
                # Check alert level if specified
                if "level" in alert_condition and alert_data.get("level") != alert_condition["level"]:
                    continue
                    
                # Check alert type if specified
                if "type" in alert_condition and alert_data.get("type") != alert_condition["type"]:
                    continue
                    
                # Check alert source if specified
                if "source" in alert_condition and alert_data.get("source") != alert_condition["source"]:
                    continue

        if matches:
            logger.info(f"[AirdropWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches

    async def initialize_cache(self, targets: List[str]):
        """Initialize cache for new airdrop targets"""
        try:
            for target in targets:
                # Initialize airdrop cache for new targets
                if target not in self.airdrop_cache:
                    try:
                        # Get initial airdrop data
                        airdrop_data = await self.get_airdrop_data([target])
                        if airdrop_data and target in airdrop_data:
                            self.airdrop_cache[target] = airdrop_data[target].get("data", {})
                            logger.info(f"[AirdropWatcher] Initialized airdrop cache for {target}")
                    except Exception as e:
                        logger.error(f"[AirdropWatcher] Error initializing airdrop cache for {target}: {e}")
        except Exception as e:
            logger.error(f"[AirdropWatcher] Error initializing cache: {e}", exc_info=True) 