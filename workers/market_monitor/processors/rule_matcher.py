import asyncio
import logging
import json
from typing import Dict, List, Optional

from workers.market_monitor.shared.models import Rule, RuleMatch, Notification
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoJSONEncoder
from workers.market_monitor.utils.config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RuleMatcher:
    def __init__(self):
        self.redis = None
        self.watch_types = ["market", "wallet", "airdrop"]  # List of supported watch types
        self.config = get_config()

    async def start(self):
        """Start the rule matcher processor"""
        try:
            logger.info("[RuleMatcher] Initializing...")
            self.redis = await RedisClient.get_instance()
            logger.info("[RuleMatcher] Redis connection established")

            # Subscribe to rule matched events for all watch types
            for watch_type in self.watch_types:
                channel = f"{watch_type}_watch:rule_matched"
                logger.info(f"[RuleMatcher] Subscribing to {channel}")
                await self.redis.subscribe(channel, self.process_match)
                logger.info(f"[RuleMatcher] Successfully subscribed to {channel}")

            logger.info("[RuleMatcher] Processor started and running")
            # Keep the processor running
            while True:
                try:
                    await asyncio.sleep(0.1)  # Prevent tight loop
                except Exception as e:
                    logger.error(f"[RuleMatcher] Error in main loop: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[RuleMatcher] Failed to start: {e}")
            raise

    async def process_match(self, channel: str, match_data: Dict):
        """Process match from rule_matched channel"""
        try:
            logger.info(f"[RuleMatcher] Processing match data: {json.dumps(match_data, cls=MongoJSONEncoder)}")
            
            # Extract watch_type from channel
            watch_type = channel.split("_")[0]
            
            # Convert data to RuleMatch
            rule = Rule.from_dict(match_data["rule"])
            match = RuleMatch(
                rule=rule,
                match_data=match_data["match_data"]
            )
            logger.info(f"[RuleMatcher] Created RuleMatch for rule {rule.rule_id}")

            # Validate match
            if not self.validate_match(match, watch_type):
                logger.warning(f"[RuleMatcher] Invalid match data: {match_data}")
                return
            logger.info(f"[RuleMatcher] Match data validated successfully")

            # Check for duplicate notification
            notification_key = f"notify:last:{watch_type}:{rule.rule_id}"
            last_notify = await self.redis.get(notification_key)
            
            # Get current match data for comparison
            current_match = json.dumps(match.match_data, cls=MongoJSONEncoder, sort_keys=True)
            
            # Handle both string and dict data types from Redis
            if last_notify:
                try:
                    if isinstance(last_notify, bytes):
                        last_notify = last_notify.decode()
                    elif isinstance(last_notify, dict):
                        last_notify = json.dumps(last_notify, cls=MongoJSONEncoder, sort_keys=True)
                    elif isinstance(last_notify, str):
                        pass
                    else:
                        last_notify = str(last_notify)
                        
                    if last_notify == current_match:
                        logger.info(f"[RuleMatcher] Skipping duplicate notification for rule {rule.rule_id}")
                        return
                except Exception as e:
                    logger.warning(f"[RuleMatcher] Error comparing notification data: {e}")
                    # Continue processing if comparison fails
                    
            logger.info(f"[RuleMatcher] No duplicate found, proceeding with notification")
                
            # Create notification
            notification = self.create_notification(match, watch_type)
            if notification:
                logger.info(f"[RuleMatcher] Created notification: {json.dumps(notification.to_dict(), cls=MongoJSONEncoder)}")
                
                # Publish to notification channel
                await self.redis.publish(
                    f"{watch_type}_watch:send_notify",
                    json.dumps(notification.to_dict(), cls=MongoJSONEncoder)
                )
                logger.info(f"[RuleMatcher] Published notification to {watch_type}_watch:send_notify")
                
                # Store current match data to prevent duplicates
                await self.redis.set(notification_key, current_match, 60)  # Expire after 60 seconds
                logger.info(f"[RuleMatcher] Stored match data in Redis for deduplication")
                
                logger.info(f"[RuleMatcher] Match processed successfully for rule {rule.rule_id}")
            else:
                logger.warning(f"[RuleMatcher] Failed to create notification for rule {rule.rule_id}")

        except Exception as e:
            logger.error(f"[RuleMatcher] Error processing match {match_data}: {e}", exc_info=True)

    def validate_match(self, match: RuleMatch, watch_type: str) -> bool:
        """Validate match data"""
        try:
            if not match.rule or not match.match_data:
                return False

            # Validate matches list exists
            matches = match.match_data.get("matches", [])
            if not isinstance(matches, list):
                return False

            # Validate each match based on watch_type
            for m in matches:
                if not isinstance(m, dict):
                    return False
                    
                if watch_type == "market":
                    # For price alerts, require token
                    if m.get("condition") in ["price_above", "price_below", "price_change", "price_change_24h"]:
                        if "token" not in m:
                            return False
                elif watch_type == "wallet":
                    # For wallet alerts, require wallet address
                    if m.get("condition") in ["balance_below", "balance_change", "token_transfer", "nft_transfer"]:
                        if "wallet" not in m:
                            return False
                elif watch_type == "airdrop":
                    # For airdrop alerts, require project
                    if m.get("condition") in ["airdrop_announced", "airdrop_started", "airdrop_ended"]:
                        if "project" not in m:
                            return False
                            
                # For general alerts, require message
                if m.get("condition") == "alert":
                    if "message" not in m:
                        return False

            return True

        except Exception as e:
            logger.error(f"Error validating match: {e}")
            return False

    def create_notification(self, match: RuleMatch, watch_type: str) -> Optional[Notification]:
        """Create notification from match data"""
        try:
            # Extract data
            rule = match.rule
            matches = match.match_data["matches"]

            # Build notification message
            messages = []
            for m in matches:
                condition = m.get("condition")
                msg = None  # Initialize msg variable
                
                if watch_type == "market":
                    if condition == "alert":
                        # For alert messages, use the message directly
                        msg = m.get("message", "")
                        if msg:
                            # Just use the message and link, without header
                            msg = f"• {msg}"
                        else:
                            continue
                    else:
                        token = m["token"]
                        if condition == "price_above":
                            current_price = m["value"]
                            msg = f"<b>{token}</b> price above ${m['threshold']:,.2f} (current: ${current_price:,.2f})"
                        elif condition == "price_below":
                            current_price = m["value"]
                            msg = f"<b>{token}</b> price below ${m['threshold']:,.2f} (current: ${current_price:,.2f})"
                        elif condition == "price_change":
                            change = m["value"]
                            old_price = m["old_price"]
                            new_price = m["new_price"]
                            direction = "increased" if change > 0 else "decreased"
                            msg = f"<b>{token}</b> {direction} by {abs(change):.1f}% (from ${old_price:,.2f} → ${new_price:,.2f})"
                        elif condition == "price_change_24h":
                            change = m["value"]
                            current_price = m.get("current_price", 0)
                            direction = "increased" if change > 0 else "decreased"
                            msg = f"<b>{token}</b> {direction} by {abs(change):.1f}% in 24h (current: ${current_price:,.2f})"
                        else:  # any condition
                            price = m["price"]
                            change = m["change"]
                            change_24h = m["change_24h"]
                            msg = f"<b>{token}</b>: ${price:,.2f} ({'+' if change >= 0 else ''}{change:.1f}% | {'+' if change_24h >= 0 else ''}{change_24h:.1f}% 24h)"
                
                elif watch_type == "wallet":
                    wallet = m["wallet"]
                    wallet_name = m.get("wallet_name", wallet)
                    chain = m.get("chain", "ethereum")
                    activity_type = m.get("activity_type")
                    
                    if activity_type == "native_transfer_in":
                        amount = m.get("amount", 0)
                        old_balance = m.get("old_balance", 0)
                        new_balance = m.get("new_balance", 0)
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        
                        msg = f"🔔 <b>Native Transfer (Received)</b> on <b>{chain.upper()}</b>\n"
                        msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                        msg += f"• From: <code>{m.get('from', 'Unknown')}</code> (<a href='{scan_url}/address/{m.get('from', 'Unknown')}'>View</a>)\n"
                        msg += f"• To: <code>{m.get('to', 'Unknown')}</code> (<a href='{scan_url}/address/{m.get('to', 'Unknown')}'>View</a>)\n"
                        msg += f"• Amount: {amount} {chain.upper()}\n"
                        msg += f"• Balance: {old_balance} → {new_balance}\n"
                        msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    elif activity_type == "native_transfer_out":
                        amount = m.get("amount", 0)
                        old_balance = m.get("old_balance", 0)
                        new_balance = m.get("new_balance", 0)
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        
                        msg = f"🔔 <b>Native Transfer (Sent)</b> on <b>{chain.upper()}</b>\n"
                        msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                        msg += f"• From: <code>{m.get('from', 'Unknown')}</code> (<a href='{scan_url}/address/{m.get('from', 'Unknown')}'>View</a>)\n"
                        msg += f"• To: <code>{m.get('to', 'Unknown')}</code> (<a href='{scan_url}/address/{m.get('to', 'Unknown')}'>View</a>)\n"
                        msg += f"• Amount: {amount} {chain.upper()}\n"
                        msg += f"• Balance: {old_balance} → {new_balance}\n"
                        msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    elif activity_type == "token_transfer_in":
                        token = m.get("token", "Unknown")
                        token_name = m.get("token_name", "Unknown")
                        token_symbol = m.get("token_symbol", "Unknown")
                        amount = m.get("formatted_amount", m.get("amount", 0))
                        from_address = m.get("from", "Unknown")
                        to_address = m.get("to", "Unknown")
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        
                        msg = f"🔔 <b>Token Transfer (Received)</b> on <b>{chain.upper()}</b>\n"
                        msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                        msg += f"• From: <a href='{scan_url}/address/{from_address}'>{from_address}</a>\n"
                        msg += f"• To: <a href='{scan_url}/address/{to_address}'>{to_address}</a>\n"
                        msg += f"• Type: ERC-20\n"
                        msg += f"• CA: <a href='{scan_url}/token/{token}'>{token}</a>\n"
                        msg += f"• Amount: {amount} {token_symbol} ({token_name})\n"
                        msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    elif activity_type == "token_transfer_out":
                        token = m.get("token", "Unknown")
                        token_name = m.get("token_name", "Unknown")
                        token_symbol = m.get("token_symbol", "Unknown")
                        amount = m.get("formatted_amount", m.get("amount", 0))
                        from_address = m.get("from", "Unknown")
                        to_address = m.get("to", "Unknown")
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        
                        msg = f"🔔 <b>Token Transfer (Sent)</b> on <b>{chain.upper()}</b>\n"
                        msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                        msg += f"• From: <a href='{scan_url}/address/{from_address}'>{from_address}</a>\n"
                        msg += f"• To: <a href='{scan_url}/address/{to_address}'>{to_address}</a>\n"
                        msg += f"• Type: ERC-20\n"
                        msg += f"• CA: <a href='{scan_url}/token/{token}'>{token}</a>\n"
                        msg += f"• Amount: {amount} {token_symbol} ({token_name})\n"
                        msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    elif activity_type == "token_trade":
                        token_in = m.get("token_in", "Unknown")
                        token_in_name = m.get("token_in_name", "Unknown Token")
                        token_in_symbol = m.get("token_in_symbol", "Unknown")
                        token_out = m.get("token_out", "Unknown")
                        token_out_name = m.get("token_out_name", "Unknown Token")
                        token_out_symbol = m.get("token_out_symbol", "Unknown")
                        amount_in = m.get("formatted_amount_in", m.get("amount_in", "N/A"))
                        amount_out = m.get("formatted_amount_out", m.get("amount_out", "N/A"))
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)

                        if chain == "solana":
                            if m.get("side") == "buy":
                                msg = f"🔔 <b>Buy Token</b> on <b>{chain.upper()}</b>\n"
                            else:
                                msg = f"🔔 <b>Sell Token</b> on <b>{chain.upper()}</b>\n"
                            msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                            
                            if token_in:
                                msg += f"• Token In: {token_in_name}\n" if token_in == "native" else f"• Token In: <a href='{scan_url}/token/{token_in}'>{token_in_name}</a>\n"
                                msg += f"• Amount In: {amount_in} {token_in_symbol}\n"
                                msg += f"• CA: <code>{token_in}</code>\n" if token_in != "native" else ""
                            
                            if token_out:
                                msg += f"• Token Out: {token_out_name}\n" if token_out == "native" else f"• Token Out: <a href='{scan_url}/token/{token_out}'>{token_out_name}</a>\n"
                                msg += f"• Amount Out: {amount_out} {token_out_symbol}\n"
                                msg += f"• CA: <code>{token_out}</code>\n" if token_out != "native" else ""
                            
                            msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>\n"
                            msg += f"• Dex: {m.get('dex_name', 'Unknown')}\n"
                            msg += f"• Fee: {m.get('fee', 'N/A')} SOL\n"
                        else:
                            # EVM chains
                            if token_out == "native":
                                msg = f"🔔 <b>Token Sold</b> on <b>{chain.upper()}</b>\n"
                                msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                                msg += f"• Sold: {amount_in} {token_in_symbol} ({token_in_name})\n"
                                msg += f"• Received: {amount_out} {token_out_symbol}\n"
                                msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                            else:
                                msg = f"🔔 <b>Token Swapped</b> on <b>{chain.upper()}</b>\n"
                                msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                                msg += f"• Sold: {amount_in} {token_in_symbol} ({token_in_name})\n"
                                msg += f"• Bought: {amount_out} {token_out_symbol} ({token_out_name})\n"
                                msg += f"• CA: <code>{token_out}</code>\n"
                                msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    elif activity_type == "nft_trade":
                        collection = m.get("collection", "Unknown")
                        token_id = m.get("token_id", "Unknown")
                        token_amount = m.get("token_amount", "N/A")
                        token_symbol = m.get("token_symbol", "Unknown")
                        tx_hash = m.get("tx_hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        msg = f"<b>{wallet}</b> on {chain.upper()}\n"
                        msg += f"🔸 NFT: {collection} #{token_id}\n"
                        msg += f"🔸 Amount: {token_amount} {token_symbol}\n"
                        msg += f"🔸 TX: <a href='{scan_url}{tx_hash}'>{tx_hash}</a>"
                    elif activity_type == "solana_transfer":
                        # Handle Solana native transfers
                        amount = m.get("amount", "N/A")
                        fee = m.get("fee", "N/A")
                        tx_hash = m.get("hash", "")
                        scan_url = self.config.get_scan_url(chain)
                        
                        msg = f"🔔 <b>Native Transfer</b> on <b>{chain.upper()}</b>\n"
                        msg += f"• Wallet: <a href='{scan_url}/address/{wallet}'>{wallet_name}</a>\n"
                        msg += f"• Amount: {amount} SOL\n"
                        msg += f"• Fee: {fee} SOL\n"
                        msg += f"• TX: <a href='{scan_url}/tx/{tx_hash}'>View Transaction</a>"
                    else:
                        # Default message for unknown activity type
                        msg = f"<b>{wallet}</b> on {chain.upper()}: {activity_type}"
                
                elif watch_type == "airdrop":
                    if condition == "alert":
                        # For airdrop alerts, use the message and post_link
                        msg = m.get("message", "")
                        if msg:
                            # Just use the message and link, without header
                            msg = f"• {msg}"
                    else:
                        # Skip other conditions for now
                        continue
                
                elif condition == "alert":
                    # For alert messages, use the message directly
                    msg = m.get("message", "")
                    if not msg:
                        continue
                else:
                    # Skip if no message was generated
                    continue

                if msg:  # Only add non-empty messages
                    messages.append(msg)

            if not messages:
                return None

            # Add header for airdrop notifications
            if watch_type == "airdrop":
                messages.insert(0, "🔔 <b>Airdrop Alert</b>")
            elif watch_type == "market":
                messages.insert(0, "🔔 <b>Market Alert</b>")

            return Notification(
                user=rule.notify_id,
                channel=rule.notify_channel,
                message="\n".join(messages),
                metadata={
                    "rule_id": rule.rule_id,
                    "user_id": rule.user_id,
                    "conversation_id": rule.metadata.get("conversation_id"),
                    "parse_mode": "HTML",  # Add parse_mode for HTML formatting
                    "disable_web_page_preview": True
                }
            )

        except Exception as e:
            logger.error(f"Error creating notification: {e}", exc_info=True)
            return None

    async def close(self):
        """Cleanup resources"""
        if self.redis:
            await self.redis.close()

async def main():
    """Main entry point for rule matcher"""
    matcher = RuleMatcher()
    try:
        await matcher.start()
    except KeyboardInterrupt:
        logger.info("Rule matcher shutting down")
    finally:
        await matcher.close()

if __name__ == "__main__":
    asyncio.run(main())
