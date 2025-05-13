import json
import logging
import asyncio
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
            airdrop_data = await self.get_airdrop_data(list(self.watching_targets), target_data)
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

    async def get_airdrop_data(self, targets: List[str], target_data: Dict = None) -> Dict:
        """Get current airdrop data from API"""
        try:
            # Get alert data first
            alert_url = self.config.get_alert_url()
            alert_data = {
                "crypto": list(self.watching_targets) if self.watching_targets and '*' not in self.watching_targets else [],
                "time": 10
            }
            
            logger.info(f"[AirdropWatcher] Calling alert API: {alert_url}, {alert_data}")
            alert_response = await call_api(
                alert_url,
                method="POST",
                data=alert_data,
                timeout=self.config.api["alert"]["timeout"]
            )
            
            alert_matches = []
            if alert_response and alert_response.get("success", False):
                logger.info(f"[AirdropWatcher] Alert API call successful: {alert_response}")
                # Get alert messages from response
                alert_data = alert_response.get("data", {})
                if alert_data and alert_data.get("success", False):
                    alert_messages = alert_data.get("data", [])
                    logger.info(f"[AirdropWatcher] Alert messages: {alert_messages}")
                    for alert in alert_messages:
                        logger.info(f"[AirdropWatcher] Alert: {alert}")
                        if isinstance(alert, dict) and "text" in alert:
                            # Process all alerts without token parsing
                            alert_matches.append({
                                "condition": "alert",
                                "message": alert["text"],
                                "data": alert
                            })
                            logger.info(f"[AirdropWatcher] Added alert match: {alert['text']}")
                    logger.info(f"[AirdropWatcher] Found {len(alert_matches)} alert matches")

            # Get API URL and headers from config
            api_url = self.config.get_airdrop_api_url()
            api_key = self.config.get_airdrop_api_key()
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            
            # Get data for each target
            result = {}
            for target in targets:
                try:
                    response = await call_api(
                        f"{api_url}/airdrop",
                        method="POST",
                        data={"target": target},
                        headers=headers,
                        timeout=self.config.api["airdrop"]["timeout"]
                    )
                    
                    if response and response.get("success", False):
                        result[target] = {
                            "data": response.get("data", {}),
                            "last_updated": datetime.utcnow().isoformat()
                        }
                        logger.info(f"[AirdropWatcher] Successfully fetched data for target {target}")
                    else:
                        logger.warning(f"[AirdropWatcher] Failed to get data for target {target}: {response.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"[AirdropWatcher] Error fetching data for target {target}: {e}")
                    continue
            
            # Add alert matches to result
            if alert_matches:
                result["alert_matches"] = alert_matches
                logger.info(f"[AirdropWatcher] Added {len(alert_matches)} alert matches to result")
            
            return result
            
        except Exception as e:
            logger.error(f"[AirdropWatcher] Error fetching airdrop data: {e}", exc_info=True)
            return {}

    async def evaluate_conditions(self, rule: Rule, airdrop_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against airdrop data"""
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[AirdropWatcher] Evaluating conditions for rule {rule.rule_id}: {self._serialize_to_json(condition)}")

        for target in rule.target:
            if target not in airdrop_data:
                logger.warning(f"[AirdropWatcher] Target {target} not found in airdrop data")
                continue

            data = airdrop_data[target]["data"]
            current_status = data.get("status", {})
            current_announcements = data.get("announcements", [])
            current_eligibility = data.get("eligibility", {})

            # Cache previous data for change detection
            prev_data = self.airdrop_cache.get(target, {})
            self.airdrop_cache[target] = data

            # Check for new announcements
            if "announcements" in condition:
                for announcement in current_announcements:
                    if announcement.get("is_new", False):
                        matches.append({
                            "target": target,
                            "condition": "new_announcement",
                            "message": announcement.get("message"),
                            "data": announcement
                        })

            # Check for status changes
            if "status" in condition:
                prev_status = prev_data.get("status", {})
                if current_status.get("current") != prev_status.get("current"):
                    matches.append({
                        "target": target,
                        "condition": "status_change",
                        "old_status": prev_status.get("current"),
                        "new_status": current_status.get("current"),
                        "data": current_status
                    })

            # Check for eligibility updates
            if "eligibility" in condition:
                prev_eligibility = prev_data.get("eligibility", {})
                if current_eligibility.get("requirements") != prev_eligibility.get("requirements"):
                    matches.append({
                        "target": target,
                        "condition": "eligibility_update",
                        "old_requirements": prev_eligibility.get("requirements"),
                        "new_requirements": current_eligibility.get("requirements"),
                        "data": current_eligibility
                    })

            # Check specific conditions
            if "min_reward" in condition and current_status.get("reward", 0) >= condition["min_reward"]:
                matches.append({
                    "target": target,
                    "condition": "reward_threshold",
                    "value": current_status.get("reward"),
                    "threshold": condition["min_reward"]
                })

            if "deadline" in condition:
                deadline = datetime.fromisoformat(current_status.get("deadline", ""))
                if deadline and deadline < datetime.utcnow():
                    matches.append({
                        "target": target,
                        "condition": "deadline_reached",
                        "deadline": current_status.get("deadline")
                    })

        if matches:
            logger.info(f"[AirdropWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches 