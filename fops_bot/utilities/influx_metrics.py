"""
Simple async InfluxDB metrics utility
"""

import os
import asyncio
import logging
from typing import Optional

try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS

    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global client and write API
_client: Optional[InfluxDBClient] = None
_write_api = None


def _get_client():
    """Get or create InfluxDB client"""
    global _client, _write_api

    if not INFLUX_AVAILABLE or not os.getenv("INFLUX_TOKEN"):
        return None, None

    if _client is None:
        try:
            _client = InfluxDBClient(
                url=os.getenv("INFLUX_URL", "http://localhost:8086"),
                token=os.getenv("INFLUX_TOKEN"),
                org="KitsuneHosting",
            )
            _write_api = _client.write_api(write_options=SYNCHRONOUS)
        except Exception as e:
            logger.warning(f"InfluxDB connection failed: {e}")
            return None, None

    return _client, _write_api


def send_metric(measurement: str, guild_id: int, value: int = 1, **tags):
    """Send metric to InfluxDB"""
    if not INFLUX_AVAILABLE:
        return

    client, write_api = _get_client()
    if not client or not write_api:
        return

    try:
        point = Point(measurement).tag("guild_id", str(guild_id))

        # Add any additional tags
        for key, tag_value in tags.items():
            point = point.tag(key, str(tag_value))

        point = point.field("value", value)

        write_api.write(bucket=os.getenv("INFLUX_BUCKET", "guild-stats"), record=point)
    except Exception as e:
        logger.warning(f"InfluxDB metric failed: {e}")


def close_client():
    """Close InfluxDB client"""
    global _client, _write_api

    if _client:
        try:
            _client.close()
        except Exception as e:
            logger.warning(f"Error closing InfluxDB client: {e}")
        finally:
            _client = None
            _write_api = None
