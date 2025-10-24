import redis
import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper for internal service communication"""

    def __init__(self):
        self.host = os.environ.get("REDIS_HOST", "redis")
        self.port = int(os.environ.get("REDIS_PORT", "6379"))
        self.db = int(os.environ.get("REDIS_DB", "0"))
        self._client = None

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        return self._client

    def publish_job(self, channel: str, job_data: Dict[str, Any]) -> bool:
        """Publish a job to a Redis channel"""
        try:
            message = json.dumps(job_data)
            result = self.client.publish(channel, message)
            logger.debug(
                f"Published job to {channel}: {job_data.get('job_id', 'unknown')}"
            )
            return result > 0
        except Exception as e:
            logger.error(f"Failed to publish job to {channel}: {e}")
            return False

    def set_job_status(
        self, job_id: str, status_data: Dict[str, Any], ttl: int = 3600
    ) -> bool:
        """Set job status in Redis with TTL"""
        try:
            key = f"job_status:{job_id}"
            data = json.dumps(status_data)
            result = self.client.setex(key, ttl, data)
            logger.debug(
                f"Set job status for {job_id}: {status_data.get('status', 'unknown')}"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to set job status for {job_id}: {e}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from Redis"""
        try:
            key = f"job_status:{job_id}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return None

    def delete_job_status(self, job_id: str) -> bool:
        """Delete job status from Redis"""
        try:
            key = f"job_status:{job_id}"
            result = self.client.delete(key)
            logger.debug(f"Deleted job status for {job_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete job status for {job_id}: {e}")
            return False

    def set_service_health(
        self, service_name: str, health_data: Dict[str, Any], ttl: int = 60
    ) -> bool:
        """Set service health status in Redis"""
        try:
            key = f"service_health:{service_name}"
            data = json.dumps(health_data)
            result = self.client.setex(key, ttl, data)
            logger.debug(f"Set health status for {service_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to set health status for {service_name}: {e}")
            return False

    def get_service_health(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service health status from Redis"""
        try:
            key = f"service_health:{service_name}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get health status for {service_name}: {e}")
            return None

    def queue_message(self, queue_name: str, message_data: Dict[str, Any]) -> bool:
        """Queue a message for processing"""
        try:
            message = json.dumps(message_data)
            result = self.client.lpush(queue_name, message)
            logger.debug(f"Queued message to {queue_name}")
            return result > 0
        except Exception as e:
            logger.error(f"Failed to queue message to {queue_name}: {e}")
            return False

    def dequeue_message(
        self, queue_name: str, timeout: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Dequeue a message from a queue"""
        try:
            result = self.client.brpop(queue_name, timeout=timeout)
            if result:
                _, message = result
                return json.loads(message)
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue message from {queue_name}: {e}")
            return None

    def subscribe_to_channel(self, channel: str):
        """Subscribe to a Redis channel for pub/sub"""
        try:
            pubsub = self.client.pubsub()
            pubsub.subscribe(channel)
            logger.debug(f"Subscribed to channel: {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to channel {channel}: {e}")
            return None

    def test_connection(self) -> bool:
        """Test Redis connection"""
        try:
            self.client.ping()
            logger.info("Redis connection successful")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()
