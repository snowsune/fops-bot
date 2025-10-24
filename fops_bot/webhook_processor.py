import os
import logging
import requests
import time
from utilities.redis_client import redis_client

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def process_webhook_queue():
    logger.info("Started webhook processor")
    
    while True:
        try:
            message_data = redis_client.dequeue_message("webhook_queue", timeout=5)
            
            if message_data:
                logger.info(f"Processing webhook for user: {message_data.get('user', 'unknown')}")
                
                payload = {
                    "content": message_data.get("content"),
                    "user": message_data.get("user"),
                    "discord_id": message_data.get("discord_id"),
                    "key": message_data.get("key"),
                }
                
                webhook_url = message_data.get("webhook_url")
                if not webhook_url:
                    logger.error("No webhook URL in message data")
                    continue
                
                try:
                    response = requests.post(webhook_url, json=payload, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"Successfully sent webhook for user {payload.get('user')}")
                    else:
                        logger.error(f"Failed to send webhook. Status: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error sending webhook: {e}")
            
        except Exception as e:
            logger.error(f"Error processing webhook queue: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if not redis_client.test_connection():
        logger.error("Failed to connect to Redis, exiting")
        exit(1)
    
    logger.info("Webhook processor started")
    process_webhook_queue()