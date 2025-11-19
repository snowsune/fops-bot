import redis
import json
import logging
import os
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client with automatic reconnection on disconnect."""

    def __init__(self):
        self.host = os.environ.get("REDIS_HOST", "redis")
        self.port = int(os.environ.get("REDIS_PORT", "6379"))
        self.db = int(os.environ.get("REDIS_DB", "0"))
        self._client = None

    def _connect(self):
        """Create Redis connection."""
        self._client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

    def _ensure_connected(self):
        """Ensure connection is alive, reconnect if needed."""
        for attempt in range(3):
            try:
                if self._client is None:
                    self._connect()
                self._client.ping()
                return
            except Exception as e:
                if any(
                    x in str(e).lower() for x in ["connection", "timeout", "broken"]
                ):
                    logger.warning(f"Redis reconnect attempt {attempt + 1}/3")
                    self._client = None
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                    continue
                raise

    def _call(self, func, *args, **kwargs):
        """Execute Redis operation with automatic retry."""
        for attempt in range(3):
            try:
                self._ensure_connected()
                return func(self._client, *args, **kwargs)
            except Exception as e:
                if (
                    any(
                        x in str(e).lower() for x in ["connection", "timeout", "broken"]
                    )
                    and attempt < 2
                ):
                    logger.warning(f"Redis retry {attempt + 1}/3: {e}")
                    self._client = None
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

    def reinitialize(self):
        """Force re-initialize the Redis connection."""
        logger.info("Re-initializing Redis connection")
        self._client = None
        try:
            self._connect()
            self._client.ping()
            logger.info("Redis connection re-initialized successfully")
        except Exception as e:
            logger.error(f"Failed to re-initialize Redis connection: {e}")
            self._client = None

    def test_connection(self) -> bool:
        """Test Redis connection."""
        try:
            self._ensure_connected()
            return True
        except:
            return False

    def publish_job(self, channel: str, job_data: Dict[str, Any]) -> bool:
        """Publish job to Redis channel. Reinitializes connection on failure."""
        # Try once
        try:
            self._ensure_connected()
            result = self._client.publish(channel, json.dumps(job_data))
            if result > 0:
                return True
        except Exception as e:
            logger.warning(f"Publish failed: {e}")

        # If we get here, it failed - reinitialize and try once more
        logger.info("Re-initializing Redis connection and retrying publish")
        self._client = None
        try:
            self._connect()
            self._client.ping()
            result = self._client.publish(channel, json.dumps(job_data))
            return result > 0
        except Exception as e:
            logger.error(f"Failed to publish after reinitialize: {e}")
            self._client = None
            return False

    def set_job_status(
        self, job_id: str, status_data: Dict[str, Any], ttl: int = 3600
    ) -> bool:
        """Set job status in Redis."""
        try:
            return self._call(
                lambda c: c.setex(f"job_status:{job_id}", ttl, json.dumps(status_data))
            )
        except Exception as e:
            logger.error(f"Failed to set job status: {e}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from Redis."""
        try:
            data = self._call(lambda c: c.get(f"job_status:{job_id}"))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None

    def delete_job_status(self, job_id: str) -> bool:
        """Delete job status from Redis."""
        try:
            return self._call(lambda c: c.delete(f"job_status:{job_id}")) > 0
        except Exception as e:
            logger.error(f"Failed to delete job status: {e}")
            return False

    def set_service_health(
        self, service_name: str, health_data: Dict[str, Any], ttl: int = 60
    ) -> bool:
        """Set service health status in Redis."""
        try:
            return self._call(
                lambda c: c.setex(
                    f"service_health:{service_name}", ttl, json.dumps(health_data)
                )
            )
        except Exception as e:
            logger.error(f"Failed to set health: {e}")
            return False

    def get_service_health(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service health status from Redis."""
        try:
            data = self._call(lambda c: c.get(f"service_health:{service_name}"))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get health: {e}")
            return None

    def subscribe_to_channel(self, channel: str):
        """Subscribe to Redis channel."""
        try:
            self._ensure_connected()
            pubsub = self._client.pubsub()
            pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return None


redis_client = RedisClient()
