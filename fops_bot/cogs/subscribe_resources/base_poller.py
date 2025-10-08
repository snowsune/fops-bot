import os
import discord
import logging
import time
import asyncio
from typing import List, Optional, Tuple

from discord.ext import commands, tasks
from fops_bot.models import get_session, Subscription, KeyValueStore
from cogs.subscribe_resources.filters import parse_filters, format_spoiler_post
from utilities.post_utils import Post, Posts

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

    async def cog_load(self):
        """Start the polling task when the cog loads"""
        self._poll_task = asyncio.create_task(self.poll_loop())

    async def cog_unload(self):
        """Cancel the polling task when the cog unloads"""
        if self._poll_task:
            self._poll_task.cancel()

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
            self.logger.info(f"Skipping {post.id} due to missing required tags")
            return False
        if any(tag in tags for tag in negative_filters):
            self.logger.info(f"Skipping {post.id} due to excluded tags")
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
                self.logger.error(error_msg)
                return False

            # Use NSFW site if channel is NSFW and post supports it
            if channel and hasattr(channel, "is_nsfw") and channel.is_nsfw():
                url = post.get_display_url(use_nsfw_site=True)

        message_content, should_post = format_spoiler_post(
            post.id, tags, url, None if is_pm else channel
        )
        if not should_post:
            self.logger.info(f"Skipping {post.id} due to spoiler tags")
            return False

        subtitle = "\n-# Run /manage_following to edit this feed."
        msg = f"{message_content}{subtitle}"

        # Attempt to post
        try:
            if is_pm:
                user = await self.bot.fetch_user(sub.user_id)
                await user.send(msg)
                self.logger.info(f"Posted {post.id} to user {sub.user_id}")
                return True
            else:
                if channel:
                    await channel.send(msg)
                    self.logger.info(f"Posted {post.id} to channel {sub.channel_id}")
                    return True
                else:
                    self.logger.error(f"Channel {sub.channel_id} not accessible")
                    return False
        except discord.Forbidden as e:
            self.logger.error(f"Permission denied posting to {sub.channel_id}: {e}")
            return False
        except discord.NotFound as e:
            self.logger.error(f"Channel/user not found for {sub.channel_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error posting {post.id}: {e}")
            return False

    async def poll_loop(self):
        """Main polling loop that runs continuously"""
        while True:
            interval_minutes = self.calculate_poll_interval()

            try:
                await self.poll_task_once()
            except Exception as e:
                self.logger.error(
                    f"Unhandled exception in poll_task_once: {e}", exc_info=True
                )

            self.logger.debug(
                f"{self.service_type} poller cycle complete. Waiting {interval_minutes} minutes to run again."
            )
            await asyncio.sleep(interval_minutes * 60)

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

    async def poll_task_once(self):
        """Single polling cycle - implemented by subclasses"""
        self.logger.debug(f"Running {self.service_type} poller")

        with get_session() as session:
            # Load subscriptions for this service type
            subs = (
                session.query(Subscription)
                .filter_by(service_type=self.service_type)
                .all()
            )
            self.logger.debug(f"Loaded {len(subs)} {self.service_type} subscriptions.")
            if not subs:
                return

            # Group subscriptions by search criteria
            from collections import defaultdict

            groups = defaultdict(list)
            for sub in subs:
                groups[sub.search_criteria].append(sub)
            self.logger.debug(f"Grouped into {len(groups)} search criteria groups.")

            # Select group to process (oldest last_ran)
            def group_last_ran(group):
                times = [s.last_ran or 0 for s in group]
                return min(times) if times else 0

            oldest_group = min(groups.values(), key=group_last_ran)
            search_criteria = oldest_group[0].search_criteria
            self.logger.debug(
                f"Selected group '{search_criteria}' with {len(oldest_group)} subscriptions."
            )

            # Fetch latest posts for this search criteria
            try:
                posts = await self.fetch_latest_posts(search_criteria)
                # Reset failure counter on successful fetch
                if self.consecutive_failures > 0:
                    self.logger.info(
                        f"{self.service_type} API call successful, resetting failure counter from {self.consecutive_failures}"
                    )
                    self.consecutive_failures = 0
                    self.owner_notified = False

                # Update the last poll timestamp for FA
                if self.service_type == "FurAffinity":
                    now = int(time.time())
                    kv = session.get(KeyValueStore, "fa_last_poll")
                    if kv:
                        kv.value = str(now)
                    else:
                        kv = KeyValueStore(key="fa_last_poll", value=str(now))
                        session.add(kv)
            except Exception as e:
                self.consecutive_failures += 1
                self.logger.warning(
                    f"{self.service_type} API error for {search_criteria}: {e} (failure #{self.consecutive_failures})"
                )

                # Check if we should notify the owner
                if self.consecutive_failures >= 5:
                    await self.notify_owner_of_failures(search_criteria, e)

                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after error."
                )
                return

            if not posts:
                self.logger.warning(f"No posts found for {search_criteria}.")
                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after empty result."
                )
                return

            now = int(time.time())
            self.logger.debug(f"Latest post IDs for '{search_criteria}': {posts.ids}")

            # Process each subscription in the group
            for sub in oldest_group:
                self.logger.debug(
                    f"Processing subscription {sub.id} (user {sub.user_id}, channel {sub.channel_id})"
                )

                # Determine what to do with this subscription
                posts_to_process, action, reason = self.determine_posts_to_process(
                    sub, posts
                )

                if action == "skip":
                    self.logger.debug(f"Subscription {sub.id}: {reason}")
                    sub.last_ran = now
                    continue
                elif action == "catchup":
                    self.logger.warning(f"Subscription {sub.id}: {reason}")
                    sub.last_reported_id = posts_to_process[0].id
                    sub.last_ran = now
                    continue
                elif action == "post":
                    self.logger.info(
                        f"Subscription {sub.id}: {reason} - processing {len(posts_to_process)} posts"
                    )

                    # Process posts in order (oldest first)
                    last_successful_post = None
                    for post in posts_to_process:
                        self.logger.info(f"Processing post {post.id} for sub {sub.id}")

                        # Process the post
                        post_success = await self.process_single_post(sub, post)

                        if post_success:
                            last_successful_post = post
                            self.logger.info(
                                f"Successfully processed {post.id} for sub {sub.id}"
                            )
                        else:
                            self.logger.warning(
                                f"Failed to post {post.id} for sub {sub.id}"
                            )

                    # CRITICAL: Always update the subscription to the last post we attempted
                    # This prevents infinite reposting loops
                    if last_successful_post:
                        sub.last_reported_id = last_successful_post.id
                    else:
                        # If all posts failed, still update to the last one we tried
                        sub.last_reported_id = posts_to_process[-1].id

                    sub.last_ran = now

            # Commit all updates for this group
            session.commit()
            self.logger.debug(
                f"Committed updates for {len(oldest_group)} subscriptions in group '{search_criteria}'."
            )
