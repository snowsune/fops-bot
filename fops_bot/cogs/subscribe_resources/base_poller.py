import os
import discord
import logging
import time
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from discord.ext import commands, tasks
from fops_bot.models import get_session, Subscription
from cogs.subscribe_resources.filters import parse_filters, format_spoiler_post
from cogs.guild_cog import get_guild
from utilities.post_utils import Post, Posts

from utilities.influx_metrics import send_metric
from utilities.guild_log import (
    info as guild_log_info,
    warning as guild_log_warning,
    error as guild_log_error,
)

OWNER_UID = int(os.getenv("OWNER_UID", "0"))
SPOILER_TAGS = set(os.getenv("SPOILER_TAGS", "gore bestiality noncon").split())


class BasePollerCog(commands.Cog):
    """
    Base class for all poller cogs.

    Integrates improvements from FA poller and others.
    """

    def __init__(self, bot, service_type: str):
        self.bot = bot
        self.service_type = service_type
        self.logger = logging.getLogger(f"cogs.{self.__class__.__name__.lower()}")
        self._poll_task = None
        self.consecutive_failures = 0
        self.owner_notified = False
        self._current_cycle_task: Optional[asyncio.Task] = None

    async def cog_load(self):
        """Start the polling task when the cog loads"""
        self._poll_task = asyncio.create_task(self.poll_loop())

    async def cog_unload(self):
        """Cancel the polling task when the cog unloads"""
        if self._poll_task:
            self._poll_task.cancel()
        if self._current_cycle_task:
            self._current_cycle_task.cancel()
            self._current_cycle_task = None

    async def fetch_latest_posts(self, search_criteria: str) -> Posts:
        """
        Abstract method that each platform must implement.
        Should return a Posts collection of the latest posts for the given search criteria.
        """
        raise NotImplementedError("Subclasses must implement fetch_latest_posts")

    async def notify_owner_of_failures(self, search_criteria: str, error: Exception):
        """
        Abstract method for platform-specific failure notifications.
        Should handle platform-specific error messages and owner notifications.
        """

        raise NotImplementedError("Subclasses must implement notify_owner_of_failures")

    def determine_posts_to_process(
        self, sub: Subscription, posts: Posts
    ) -> Tuple[List[Post], str, str]:
        """
        Determine which posts (if any) should be processed for this subscription.

        Returns:
            tuple: (posts_to_process, action_type, reason)
            action_type: 'post', 'skip', 'catchup', 'error'
            posts_to_process: list of Post objects to process in order (oldest first)
        """

        if sub.last_reported_id is None:
            # New subscription - post the latest post
            return [posts[0]], "post", "new_subscription"

        try:
            last_reported_idx = posts.ids.index(str(sub.last_reported_id))
            if last_reported_idx == 0:
                # We're already at the latest post
                return [], "skip", "no_new_posts"

            # Get all posts that are newer than what we've reported
            # Process them in order from oldest to newest
            posts_to_process = posts.posts[:last_reported_idx]

            # Vixi reverses to print the list in the right order lol
            posts_to_process = list(reversed(posts_to_process))
            return (
                posts_to_process,
                "post",
                f"new_posts_available: {len(posts_to_process)} posts",
            )

        except ValueError:
            # Last reported ID not found in latest posts
            # This could mean the most recent post was deleted or we're way behind
            # Just move to the latest post and log a warning
            return [posts[0]], "catchup", "post_deleted_or_missing"

    async def fetch_channel_safely(
        self, channel_id: str, subscription_id
    ) -> Tuple[Optional[discord.TextChannel], Optional[str], Optional[str]]:
        """
        Safely fetch a Discord channel.

        Returns:
            tuple: (channel_object, error_type, error_message)
        """

        try:
            self.logger.debug(
                f"Fetching channel {channel_id} for subscription {subscription_id}"
            )
            channel = await self.bot.fetch_channel(int(channel_id))
            return channel, None, None

        except discord.Forbidden as e:
            error_msg = (
                f"PERMISSION DENIED: Cannot access channel {channel_id} for subscription {subscription_id}. "
                f"Bot lacks permissions to view this channel. Error: {e}"
            )
            return None, "forbidden", error_msg

        except discord.NotFound as e:
            error_msg = (
                f"CHANNEL NOT FOUND: Channel {channel_id} for subscription {subscription_id} no longer exists. "
                f"Channel may have been deleted. Error: {e}"
            )
            return None, "not_found", error_msg

        except Exception as e:
            error_msg = f"UNEXPECTED ERROR fetching channel {channel_id} for subscription {subscription_id}: {e}"
            return None, "unexpected", error_msg

    async def process_single_post(self, sub: Subscription, post: Post) -> bool:
        """
        Process a single post for a subscription.

        Returns:
            bool: True if post was successfully processed, False otherwise
        """

        # Apply filters
        tags = set(post.tags)
        positive_filters, negative_filters = parse_filters(sub.filters)

        if positive_filters and not (tags & positive_filters):
            guild_log_info(
                self.logger,
                sub.guild_id,
                f"Skipping {post.id} due to missing required tags ({positive_filters} not in {tags})",
            )
            return False
        if any(tag in tags for tag in negative_filters):
            matched = {tag for tag in negative_filters if tag in tags}
            guild_log_info(
                self.logger,
                sub.guild_id,
                f"Skipping {post.id} due to excluded tags (found {matched} in {tags})",
            )
            return False

        # Prepare message
        url = post.url
        channel = None

        # Handle PM vs channel posting
        is_pm = getattr(sub, "is_pm", False)
        if not is_pm:
            channel, error_type, error_msg = await self.fetch_channel_safely(
                str(sub.channel_id), sub.id
            )
            if error_type:
                guild_log_error(self.logger, sub.guild_id, error_msg)
                return False

            # Use NSFW site if channel is NSFW and post supports it
            if channel and hasattr(channel, "is_nsfw") and channel.is_nsfw():
                url = post.get_display_url(use_nsfw_site=True)

        message_content, should_post = format_spoiler_post(
            post.id, tags, url, None if is_pm else channel
        )
        if not should_post:
            guild_log_info(
                self.logger,
                sub.guild_id,
                f"Skipping {post.id} due to spoiler tags",
            )
            return False

        subtitle = "\n-# Visit [snowsune.net/fops](https://snowsune.net/fops/redirect/) to manage this feed."
        msg = f"{message_content}{subtitle}"

        # Check if guild is pawsed!
        if not is_pm and sub.guild_id:
            guild_settings = get_guild(sub.guild_id)
            if guild_settings and guild_settings.is_frozen():
                msg = f"Guild {sub.guild_id} is FROZEN - skipping post {post.id} to channel {sub.channel_id}"
                guild_log_warning(self.logger, sub.guild_id, msg)
                # Return True to mark as "processed" so IDs get updated
                # This prevents spam when the guild is unfrozen
                return True

        # Attempt to post
        try:
            if is_pm:
                user = await self.bot.fetch_user(sub.user_id)
                await user.send(msg)
                guild_log_info(
                    self.logger,
                    sub.guild_id,
                    f"Posted {post.id} to user {sub.user_id} ({sub.service_type} for {sub.search_criteria})",
                )
                return True
            else:
                if channel:
                    await channel.send(msg)
                    guild_log_info(
                        self.logger,
                        sub.guild_id,
                        f"Posted {post.id} to channel {sub.channel_id} ({sub.service_type} for {sub.search_criteria})",
                    )
                    return True
                else:
                    guild_log_error(
                        self.logger,
                        sub.guild_id,
                        f"Channel {sub.channel_id} not accessible",
                    )
                    return False
        except discord.Forbidden as e:
            guild_log_error(
                self.logger,
                sub.guild_id,
                f"Permission denied posting to {sub.channel_id}: {e}",
            )
            return False
        except discord.NotFound as e:
            guild_log_error(
                self.logger,
                sub.guild_id,
                f"Channel/user not found for {sub.channel_id}: {e}",
            )
            return False
        except Exception as e:
            guild_log_error(
                self.logger,
                sub.guild_id,
                f"Error posting {post.id}: {e}",
            )
            return False

    async def poll_loop(self):
        """Main polling loop that runs continuously"""
        while True:
            interval_minutes = await asyncio.to_thread(self.calculate_poll_interval)
            self.logger.debug(
                f"Polling {self.service_type} every {interval_minutes} minutes"
            )

            self._schedule_poll_cycle()

            self.logger.debug(
                f"{self.service_type} poller cycle complete. Waiting {interval_minutes} minutes to run again."
            )
            await asyncio.sleep(interval_minutes * 60)

    def _schedule_poll_cycle(self):
        if self._current_cycle_task and not self._current_cycle_task.done():
            self.logger.debug(
                f"Previous {self.service_type} poll cycle still running; skipping new cycle scheduling."
            )
            return

        self._current_cycle_task = asyncio.create_task(
            self._run_poll_cycle(), name=f"{self.service_type}_poll_cycle"
        )
        self._current_cycle_task.add_done_callback(self._handle_cycle_completion)

    async def _run_poll_cycle(self):
        try:
            await self.poll_task_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(
                f"Unhandled exception in poll_task_once: {e}", exc_info=True
            )

    def _handle_cycle_completion(self, task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            self.logger.debug(f"{self.service_type} poll cycle cancelled.")
        except Exception as e:
            self.logger.error(
                f"{self.service_type} poll cycle completed with error: {e}",
                exc_info=True,
            )

    def calculate_poll_interval(self) -> int:
        """Calculate the polling interval based on number of subscriptions"""
        try:
            with get_session() as session:
                subs = (
                    session.query(Subscription)
                    .filter_by(service_type=self.service_type)
                    .all()
                )
                num_subs = len(subs)
                if num_subs > 0:
                    return max(1, 60 // num_subs)
                else:
                    return 5
        except Exception as e:
            self.logger.error(f"Error calculating poll interval: {e}")
            return 5

    @dataclass
    class SubscriptionSnapshot:
        id: int
        user_id: Optional[int]
        channel_id: Optional[int]
        guild_id: Optional[int]
        search_criteria: str
        service_type: str
        filters: Optional[str]
        last_reported_id: Optional[str]
        last_ran: Optional[int]
        is_pm: bool

    async def poll_task_once(self):
        """Single polling cycle - implemented by subclasses"""
        self.logger.debug(f"Running {self.service_type} poller")

        load_result = await asyncio.to_thread(self._load_oldest_subscription_group)
        if not load_result:
            self.logger.debug(f"No {self.service_type} subscriptions to process.")
            return

        search_criteria, oldest_group = load_result
        self.logger.debug(
            f"Selected group '{search_criteria}' with {len(oldest_group)} subscriptions."
        )

        # Fetch latest posts for this search criteria
        try:
            posts = await self.fetch_latest_posts(search_criteria)
            if self.consecutive_failures > 0:
                self.logger.info(
                    f"{self.service_type} API call successful, resetting failure counter from {self.consecutive_failures}"
                )
                self.consecutive_failures = 0
                self.owner_notified = False

        except Exception as e:
            await self._handle_api_failure(oldest_group, search_criteria, e)
            return

        if not posts:
            self.logger.warning(f"No posts found for {search_criteria}.")
            now = int(time.time())
            await asyncio.to_thread(
                self._persist_subscription_updates,
                [(sub.id, {"last_ran": now}) for sub in oldest_group],
            )
            self.logger.debug(
                f"Marked {len(oldest_group)} subscriptions as checked after empty result."
            )
            return

        now = int(time.time())
        self.logger.debug(f"Latest post IDs for '{search_criteria}': {posts.ids}")

        guild_cache: Dict[int, Optional[object]] = {}
        updates = []

        for sub in oldest_group:
            self.logger.debug(
                f"Processing Subscription {sub.id} ({sub.search_criteria}) (user {sub.user_id}, channel {sub.channel_id})"
            )

            is_pm = getattr(sub, "is_pm", False)
            if sub.guild_id is not None and not is_pm:
                if sub.guild_id not in guild_cache:
                    guild_cache[sub.guild_id] = get_guild(sub.guild_id)
                guild_settings = guild_cache[sub.guild_id]
                if not guild_settings or not guild_settings.nsfw():
                    guild_log_info(
                        self.logger,
                        sub.guild_id,
                        f"Skipping Subscription {sub.id} ({sub.search_criteria}) because NSFW is disabled",
                    )
                    updates.append((sub.id, {"last_ran": now}))
                    continue

            posts_to_process, action, reason = self.determine_posts_to_process(
                sub, posts
            )

            if action == "skip":
                self.logger.debug(
                    f"Subscription {sub.id} ({sub.search_criteria}): {reason}"
                )
                updates.append((sub.id, {"last_ran": now}))
                continue
            elif action == "catchup":
                guild_log_warning(
                    self.logger,
                    sub.guild_id,
                    f"Subscription {sub.id} ({sub.search_criteria}): {reason}",
                )
                updates.append(
                    (
                        sub.id,
                        {"last_reported_id": posts_to_process[0].id, "last_ran": now},
                    )
                )
                continue
            elif action == "post":
                guild_log_info(
                    self.logger,
                    sub.guild_id,
                    f"Subscription {sub.id} ({sub.search_criteria}): {reason} - processing {len(posts_to_process)} posts",
                )

                last_successful_post = None
                for post in posts_to_process:
                    guild_log_info(
                        self.logger,
                        sub.guild_id,
                        f"Processing post {post.id} for sub {sub.id}",
                    )

                    post_success = await self.process_single_post(sub, post)

                    if post_success:
                        last_successful_post = post
                        guild_log_info(
                            self.logger,
                            sub.guild_id,
                            f"Successfully processed {post.id} for sub {sub.id}",
                        )
                        send_metric(
                            "auto_post",
                            sub.guild_id or 0,
                            sub_id=str(sub.id),
                            post_id=str(post.id),
                        )
                    else:
                        guild_log_warning(
                            self.logger,
                            sub.guild_id,
                            f"Failed to post {post.id} for sub {sub.id}",
                        )

                if not posts_to_process:
                    updates.append((sub.id, {"last_ran": now}))
                    continue

                if last_successful_post:
                    updates.append(
                        (
                            sub.id,
                            {
                                "last_reported_id": last_successful_post.id,
                                "last_ran": now,
                            },
                        )
                    )
                else:
                    updates.append(
                        (
                            sub.id,
                            {
                                "last_reported_id": posts_to_process[-1].id,
                                "last_ran": now,
                            },
                        )
                    )

        if updates:
            await asyncio.to_thread(self._persist_subscription_updates, updates)
            self.logger.debug(
                f"Committed updates for {len(updates)} subscriptions in group '{search_criteria}'."
            )

    def _load_oldest_subscription_group(self):
        from collections import defaultdict

        with get_session() as session:
            subs = (
                session.query(Subscription)
                .filter_by(service_type=self.service_type)
                .all()
            )

            if not subs:
                return None

            groups = defaultdict(list)
            for sub in subs:
                snapshot = self.SubscriptionSnapshot(
                    id=sub.id,
                    user_id=sub.user_id,
                    channel_id=sub.channel_id,
                    guild_id=sub.guild_id,
                    search_criteria=sub.search_criteria,
                    service_type=sub.service_type,
                    filters=sub.filters,
                    last_reported_id=(
                        str(sub.last_reported_id)
                        if sub.last_reported_id is not None
                        else None
                    ),
                    last_ran=sub.last_ran,
                    is_pm=getattr(sub, "is_pm", False),
                )
                groups[sub.search_criteria].append(snapshot)

            def group_last_ran(group):
                times = [s.last_ran or 0 for s in group]
                return min(times) if times else 0

            oldest_group = min(groups.values(), key=group_last_ran)
            search_criteria = oldest_group[0].search_criteria
            return search_criteria, oldest_group

    def _persist_subscription_updates(
        self, updates: List[Tuple[int, Dict[str, object]]]
    ):
        if not updates:
            return

        ids = [sub_id for sub_id, _ in updates]
        update_map = {sub_id: fields for sub_id, fields in updates}

        with get_session() as session:
            db_subs = session.query(Subscription).filter(Subscription.id.in_(ids)).all()
            for db_sub in db_subs:
                fields = update_map.get(db_sub.id, {})
                for key, value in fields.items():
                    setattr(db_sub, key, value)
            session.commit()

    async def _handle_api_failure(
        self,
        oldest_group: List["BasePollerCog.SubscriptionSnapshot"],
        search_criteria: str,
        error: Exception,
    ):
        self.consecutive_failures += 1
        self.logger.warning(
            f"{self.service_type} API error for {search_criteria}: {error} (failure #{self.consecutive_failures})"
        )

        if self.consecutive_failures >= 5:
            await self.notify_owner_of_failures(search_criteria, error)

        now = int(time.time())
        await asyncio.to_thread(
            self._persist_subscription_updates,
            [(sub.id, {"last_ran": now}) for sub in oldest_group],
        )
        self.logger.debug(
            f"Marked {len(oldest_group)} subscriptions as checked after error."
        )
