import asyncio
import json
import logging
from typing import NoReturn

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from app.config.redis import get_redis_client
from app.websocket.connection_manager import manager

logger = logging.getLogger("chat.redis_listener")

async def listen_to_redis() -> None:
    channel_pattern = "conversation:*"
    logger.info(f"Initializing Redis listener on pattern: {channel_pattern}")

    while True:
        pubsub: PubSub | None = None
        try:
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub()
            await pubsub.psubscribe(channel_pattern)
            logger.info(f"Redis listener successfully subscribed to {channel_pattern}")

            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue

                raw_data = message.get("data")
                channel = message.get("channel")

                if not raw_data or not channel:
                    continue
            
                try:
                    conversation_id = channel.split(":", 1)[1]
                except IndexError:
                    logger.warning(f"Malformed channel name received: {channel}")
                    continue
            
                try:
                    event_data = json.loads(raw_data)
                except (json.JSONDecodeError, TypeError) as err:
                    logger.error(f"Failed to decode JSON from Redis channel {channel}: {err}")
                    continue

                try:
                    await manager.broadcast_to_conversation(conversation_id, event_data)
                except Exception as err:
                    logger.error("Error broadcasting event to conversation %s: %s", conversation_id, err, exc_info=True)
        
        except asyncio.CancelledError:
            logger.info("Redis listener task received cancellation request.")
            if pubsub:
                try:
                    await pubsub.punsubscribe(channel_pattern)
                    await pubsub.close()
                except Exception:
                    pass
            break

        except Exception as err:
            logger.critical("Unexpected error in Redis listener: %s. Retrying in 5 seconds...", err, exc_info=True)
            if pubsub:
                try:
                    await pubsub.close()
                except Exception:
                    pass
            await asyncio.sleep(5.0)