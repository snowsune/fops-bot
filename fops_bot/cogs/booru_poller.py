import os
import discord
import logging
import time
import asyncio

from discord.ext import commands
from fops_bot.models import get_session, Subscription
from datetime import datetime, timezone
from fops_bot.cogs.subscribe_resources.filters import parse_filters
from fops_bot.scripts.Booru_Scripts import booru_utils

BOORU_URL = os.getenv("BOORU_URL", "https://booru.kitsunehosting.net")
BOORU_API_KEY = os.getenv("BOORU_KEY")
BOORU_USERNAME = os.getenv("BOORU_USER")


class BooruPollerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._booru_poll_task = None

    async def cog_load(self):
        self._booru_poll_task = asyncio.create_task(self.booru_poll_loop())

    async def cog_unload(self):
        if self._booru_poll_task:
            self._booru_poll_task.cancel()

    async def booru_poll_loop(self):
        while True:
            interval_minutes = 5  # fallback default
            try:
                with get_session() as session:
                    booru_subs = (
                        session.query(Subscription)
                        .filter_by(service_type="BixiBooru")
                        .order_by(Subscription.id)
                        .all()
                    )
                    num_subs = len(booru_subs)
                    if num_subs > 0:
                        interval_minutes = max(1, 60 // num_subs)
                    else:
                        interval_minutes = 5
            except Exception as e:
                self.logger.error(f"Error calculating Booru poll interval: {e}")
                interval_minutes = 5

            try:
                await self.booru_poll_task_once()
            except Exception as e:
                self.logger.error(
                    f"Unhandled exception in booru_poll_task_once: {e}", exc_info=True
                )
            self.logger.debug(
                f"Booru poller cycle complete. Waiting {interval_minutes} minutes to run again."
            )
            await asyncio.sleep(interval_minutes * 60)

    async def booru_poll_task_once(self):
        self.logger.debug("Running Booru poller")
        with get_session() as session:
            booru_subs = (
                session.query(Subscription).filter_by(service_type="BixiBooru").all()
            )
            self.logger.debug(f"Loaded {len(booru_subs)} Booru subscriptions.")
            if not booru_subs:
                return

            from collections import defaultdict

            groups = defaultdict(list)
            for sub in booru_subs:
                groups[sub.search_criteria].append(sub)
            self.logger.debug(f"Grouped into {len(groups)} tag groups.")

            def group_last_ran(group):
                times = [s.last_ran or 0 for s in group]
                return min(times) if times else 0

            oldest_group = min(groups.values(), key=group_last_ran)
            search_criteria = oldest_group[0].search_criteria
            self.logger.debug(
                f"Selected group for tag '{search_criteria}' with {len(oldest_group)} subscriptions."
            )

            # Fetch latest posts for the tag
            try:
                posts = booru_utils.fetch_images_with_tag(
                    search_criteria,
                    BOORU_URL,
                    BOORU_API_KEY,
                    BOORU_USERNAME,
                    limit=5,
                )
            except Exception as e:
                self.logger.warning(f"Booru API error for {search_criteria}: {e}")
                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after error."
                )
                return
            if not posts:
                self.logger.warning(f"No posts for {search_criteria}.")
                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after empty posts."
                )
                return

            latest_posts = posts[:5]
            ids = [str(post["id"]) for post in latest_posts]
            now = int(time.time())
            self.logger.debug(f"Latest post IDs for '{search_criteria}': {ids}")

            for sub in oldest_group:
                self.logger.debug(
                    f"Processing subscription {sub.id} (user {sub.user_id}, channel {sub.channel_id})"
                )
                if sub.last_reported_id is None:
                    new_ids = ids[:1]
                    self.logger.warning(
                        f"Subscription is new, fast-forwarding id to {new_ids}."
                    )
                elif sub.last_reported_id in ids:
                    new_ids = ids[: ids.index(sub.last_reported_id)]
                else:
                    new_ids = ids
                self.logger.debug(f"New IDs to process for sub {sub.id}: {new_ids}")

                positive_filters, negative_filters = parse_filters(sub.filters)
                self.logger.debug(
                    f"Filters for sub {sub.id}: +{positive_filters}, -{negative_filters}"
                )

                for idx, post_id in enumerate(reversed(new_ids)):
                    try:
                        post = next(
                            (p for p in latest_posts if str(p["id"]) == post_id), None
                        )
                        if not post:
                            continue
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch post for {post_id}: {e}")
                        continue
                    tags = set(post.get("tag_string", "").split())
                    tags = {t.lower() for t in tags}

                    rating = post.get("rating", None)
                    if rating:
                        rating = rating.lower()
                        if rating == "s":
                            tags.add("rating:safe")
                        elif rating == "e":
                            tags.add("rating:explicit")
                        elif rating == "q":
                            tags.add("rating:questionable")
                        else:
                            self.logger.warning(
                                f"Unknown rating {rating} in post {post['id']}."
                            )
                            tags.add("rating:unknown")

                    self.logger.debug(f"Post {post_id} tags: {tags}")
                    if positive_filters and not (tags & positive_filters):
                        self.logger.info(
                            f"Skipping {post_id} due to missing required tags: {positive_filters} (tags: {tags})"
                        )
                        continue
                    if any(tag in tags for tag in negative_filters):
                        self.logger.info(
                            f"Skipping {post_id} due to excluded tags: {negative_filters} (tags: {tags})"
                        )
                        continue

                    url = f"{BOORU_URL}/posts/{post_id}"
                    channel = None

                    if sub.is_pm:
                        pass  # TODO: PM support if needed
                    else:
                        channel = await self.bot.fetch_channel(int(sub.channel_id))

                    subtitle = "\n-# Run /manage_following to edit this feed."
                    msg = f"{url}{subtitle}"

                    try:
                        if sub.is_pm:
                            self.logger.info(
                                f"Processing {post_id} in {new_ids} for user {sub.user_id}"
                            )
                            user = await self.bot.fetch_user(sub.user_id)
                            await user.send(msg)
                        else:
                            self.logger.info(
                                f"Processing {post_id} in {new_ids} for channel {sub.channel_id}"
                            )
                            if channel:
                                try:
                                    await channel.send(msg)
                                except Exception as e:
                                    self.logger.error(
                                        f"Error posting Booru update to channel {sub.channel_id}: {e}"
                                    )
                            else:
                                self.logger.error(
                                    f"Channel {sub.channel_id} not found for sub {sub.id}"
                                )
                    except Exception as e:
                        self.logger.error(f"Error posting Booru update: {e}")
                if new_ids:
                    sub.last_reported_id = new_ids[0]
                sub.last_ran = now
                self.logger.debug(
                    f"Updated last_reported_id and last_ran for sub {sub.id}"
                )
            session.commit()
            self.logger.debug(
                f"Committed updates for {len(oldest_group)} subscriptions in group '{search_criteria}'."
            )


async def setup(bot):
    await bot.add_cog(BooruPollerCog(bot))
