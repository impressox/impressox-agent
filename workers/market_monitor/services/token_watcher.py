# services/token_watcher.py

import asyncio
import json
import logging
from typing import Dict, List, Optional
from bson import ObjectId

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.utils.api import call_api
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)

class TokenWatcher(BaseWatcher):
    def __init__(self):
        super().__init__()
        self.price_cache = {}  # Cache token prices to detect changes
        self.watch_type = "token"
        self.config = get_config()

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

    async def get_alert_data(self) -> List[Dict]:
        """Get alert data from alert API"""
        try:
            alert_url = self.config.get_alert_url()
            alert_data = {
                "level": "0",
                "crypto": list(self.watching_targets) if self.watching_targets else []
            }
            
            logger.info(f"[TokenWatcher] Calling alert API: {alert_url}, {alert_data}")
            response = await call_api(
                alert_url,
                method="POST",
                data=alert_data,
                timeout=self.config.api["alert"]["timeout"]
            )
            
            if response and response.get("success", False):
                logger.info(f"[TokenWatcher] Alert API call successful: {response}")
                # Get alert messages from response
                alert_data = response.get("data", {})
                if alert_data and alert_data.get("success", False):
                    alert_messages = alert_data.get("data", [])
                    logger.info(f"[TokenWatcher] Alert messages: {alert_messages}")
                    matches = []
                    for alert in alert_messages:
                        logger.info(f"[TokenWatcher] Alert: {alert}")
                        if isinstance(alert, dict) and "text" in alert:
                            # Process all alerts without token parsing
                            matches.append({
                                "condition": "alert",
                                "message": alert["text"],
                                "data": alert
                            })
                            logger.info(f"[TokenWatcher] Added alert match: {alert['text']}")
                    logger.info(f"[TokenWatcher] Found {len(matches)} alert matches")
                    return matches
                else:
                    logger.error(f"[TokenWatcher] Alert API call failed: {response.get('error', 'Unknown error')}")
                    return []
            else:
                logger.error(f"[TokenWatcher] Alert API call failed: {response.get('error', 'Unknown error')}")
                return []
        except Exception as e:
            logger.error(f"[TokenWatcher] Error calling alert API: {e}")
            return []

    async def watch_targets(self):
        """Watch token prices and check conditions"""
        try:
            # Get token data
            logger.info(f"[TokenWatcher] Checking prices for tokens: {list(self.watching_targets)}")
            
            # Get target_data from active rules
            target_data = {}
            for token in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:token:{token}")
                    if not rules:
                        logger.warning(f"[TokenWatcher] No rules found for token {token}")
                        continue
                        
                    for rule_id, rule_json in rules.items():
                        try:
                            rule_dict = self._deserialize_from_json(rule_json)
                            logger.debug(f"[TokenWatcher] Deserialized rule for token {token}: {rule_dict}")
                            rule = Rule.from_dict(rule_dict)
                            if rule.target_data:
                                target_data.update(rule.target_data)
                            break  # Only need data from one rule
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.error(f"[TokenWatcher] Error decoding rule JSON for token {token}, rule {rule_id}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[TokenWatcher] Error getting rules for token {token}: {e}")
                    continue

            # Get token data from CoinGecko using coin_gc_id
            token_data = await self.get_token_data(list(self.watching_targets), target_data)
            if not token_data:
                logger.warning("[TokenWatcher] No token data received from API")
                token_data = {}  # Set empty dict instead of returning

            logger.info(f"[TokenWatcher] Received token data: {self._serialize_to_json(token_data)}")

            # Get alert data using original symbols
            alert_matches = await self.get_alert_data()
            if alert_matches:
                logger.info(f"[TokenWatcher] Received {len(alert_matches)} alert messages")

            # Get all active token rules
            active_rules = []
            for token in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:token:{token}")
                    if not rules:
                        continue
                        
                    logger.info(f"[TokenWatcher] Found {len(rules)} active rules for {token}")
                    for rule_id, rule_json in rules.items():
                        try:
                            rule_dict = self._deserialize_from_json(rule_json)
                            logger.debug(f"[TokenWatcher] Deserialized rule for token {token}: {rule_dict}")
                            rule = Rule.from_dict(rule_dict)
                            active_rules.append(rule)
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.error(f"[TokenWatcher] Error decoding rule JSON for token {token}, rule {rule_id}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[TokenWatcher] Error getting rules for token {token}: {e}")
                    continue

            # Check conditions for each rule
            if active_rules:
                logger.info(f"[TokenWatcher] Checking {len(active_rules)} rules against token data")
                # Combine token_data and alert_matches into target_data
                combined_data = {
                    "token_data": token_data,
                    "alert_matches": alert_matches
                }
                await self.check_rules(active_rules, combined_data)
            else:
                logger.warning("[TokenWatcher] No active rules found for watching tokens")

        except Exception as e:
            logger.error(f"[TokenWatcher] Error watching tokens: {e}", exc_info=True)

    async def get_token_data(self, tokens: List[str], target_data: Dict = None) -> Dict:
        """Get current token data from CoinGecko"""
        try:
            # Get CoinGecko IDs from target_data
            token_ids = []
            token_mapping = {}  # Map CoinGecko IDs back to original symbols
            logger.debug(f"[TokenWatcher] Target data: {target_data}")
            for token in tokens:
                if target_data and token in target_data:
                    coin_gc_id = target_data[token].get("coin_gc_id")
                    if coin_gc_id:
                        token_ids.append(coin_gc_id)
                        token_mapping[coin_gc_id] = token
                        logger.debug(f"[TokenWatcher] Mapped {token} to CoinGecko ID: {coin_gc_id}")
                    else:
                        logger.warning(f"[TokenWatcher] No coin_gc_id found for token {token}")
                        token_ids.append(token.lower())  # Fallback to lowercase symbol
                        token_mapping[token.lower()] = token
                        logger.debug(f"[TokenWatcher] Using lowercase symbol for {token}: {token.lower()}")
                else:
                    token_ids.append(token.lower())  # Fallback to lowercase symbol
                    token_mapping[token.lower()] = token
                    logger.debug(f"[TokenWatcher] Using lowercase symbol for {token}: {token.lower()}")

            # Join tokens with comma for API call
            token_ids_str = ','.join(token_ids)
            logger.info(f"[TokenWatcher] Fetching data from CoinGecko for tokens: {token_ids_str}")
            
            # Get API URL and headers from config
            api_url = self.config.get_coingecko_url()
            api_key = self.config.get_coingecko_api_key()
            headers = {"x-cg-demo-api-key": api_key} if api_key else {}
            
            logger.info(f"[TokenWatcher] Calling CoinGecko API: {api_url}/simple/price")
            response = await call_api(
                f"{api_url}/simple/price",
                method="GET",
                params={
                    "ids": token_ids_str,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true"
                },
                # headers=headers
            )
            
            logger.info(f"[TokenWatcher] CoinGecko API response: {self._serialize_to_json(response)}")
            
            if not response:
                logger.error("[TokenWatcher] Empty response from CoinGecko API")
                return {}
                
            if not response.get("success", False):
                logger.error(f"[TokenWatcher] API call failed: {response.get('error', 'Unknown error')}")
                return {}
                
            data = response.get("data", {})
            if not data:
                logger.error("[TokenWatcher] No data in API response")
                return {}
                
            # Convert CoinGecko IDs back to original symbols
            result = {}
            for coin_id, price_data in data.items():
                original_symbol = token_mapping.get(coin_id)
                if original_symbol:
                    result[original_symbol] = price_data
                    logger.debug(f"[TokenWatcher] Mapped CoinGecko ID {coin_id} back to {original_symbol}")
                else:
                    logger.warning(f"[TokenWatcher] No mapping found for CoinGecko ID: {coin_id}")
                    # Try to find a case-insensitive match
                    for token in tokens:
                        if token.lower() == coin_id.lower():
                            result[token] = price_data
                            logger.debug(f"[TokenWatcher] Found case-insensitive match for {coin_id}: {token}")
                            break
            
            logger.info(f"[TokenWatcher] Processed token data: {self._serialize_to_json(result)}")
            return result
            
        except Exception as e:
            logger.error(f"[TokenWatcher] Error fetching token data: {e}", exc_info=True)
            return {}

    async def evaluate_conditions(self, rule: Rule, target_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against token data"""
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[TokenWatcher] Evaluating conditions for rule {rule.rule_id}: {self._serialize_to_json(condition)}")

        # Get token data and alert matches from combined data
        token_data = target_data.get("token_data", {})
        alert_matches = target_data.get("alert_matches", [])

        # First check alert matches
        for alert in alert_matches:
            # The alert structure from get_alert_data has:
            # - condition: "alert"
            # - message: alert text
            # - data: original alert data
            alert_data = alert.get("data", {})
            
            # Check if this alert is for any of our target tokens
            is_target_alert = False
            for token in rule.target:
                # Check if token is mentioned in the alert message
                if token.lower() in alert["message"].lower():
                    is_target_alert = True
                    logger.info(f"[TokenWatcher] Alert match found for token {token}: {alert['message']}")
                    matches.append({
                        "token": token,
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

        # Then check price conditions
        for token in rule.target:
            if token not in token_data:
                logger.warning(f"[TokenWatcher] Token {token} not found in token data")
                continue

            data = token_data[token]
            price = data.get("usd", 0)
            change_24h = data.get("usd_24h_change", 0)
            volume_24h = data.get("usd_24h_vol", 0)

            # Cache previous price for change detection
            prev_price = self.price_cache.get(token, price)
            self.price_cache[token] = price
            price_change = ((price - prev_price) / prev_price * 100) if prev_price > 0 else 0

            logger.info(f"[TokenWatcher] Token {token} - Current price: {price}, 24h change: {change_24h}%, Price change: {price_change}%")

            # Check price conditions
            if "gt" in condition and price > condition["gt"]:
                logger.info(f"[TokenWatcher] Price above threshold: {price} > {condition['gt']}")
                matches.append({
                    "token": token,
                    "condition": "price_above",
                    "value": price,
                    "threshold": condition["gt"]
                })
            elif "lt" in condition and price < condition["lt"]:
                logger.info(f"[TokenWatcher] Price below threshold: {price} < {condition['lt']}")
                matches.append({
                    "token": token,
                    "condition": "price_below",
                    "value": price,
                    "threshold": condition["lt"]
                })

            # Check significant price changes
            if abs(price_change) > 5:  # 5% change threshold
                logger.info(f"[TokenWatcher] Significant price change detected: {price_change}%")
                matches.append({
                    "token": token,
                    "condition": "price_change",
                    "value": price_change,
                    "old_price": prev_price,
                    "new_price": price
                })

            # Check 24h changes
            if abs(change_24h) > 10:  # 10% 24h change threshold
                logger.info(f"[TokenWatcher] Significant 24h change detected: {change_24h}%")
                matches.append({
                    "token": token,
                    "condition": "price_change_24h",
                    "value": change_24h
                })

        if matches:
            logger.info(f"[TokenWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches 