import os
import faapi
import discord
import logging
import time
import asyncio

from discord.ext import commands, tasks
from fops_bot.models import get_session, Subscription, KeyValueStore
from datetime import datetime, timezone
from requests.cookies import RequestsCookieJar
from cogs.subscribe_resources.filters import parse_filters, format_spoiler_post

FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")
OWNER_UID = int(os.getenv("OWNER_UID", "0"))

SPOILER_TAGS = set(os.getenv("SPOILER_TAGS", "gore bestiality noncon").split())


class FA_PollerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._fa_poll_task = None
        self.consecutive_failures = 0
        self.owner_notified = False

    async def cog_load(self):
        self._fa_poll_task = asyncio.create_task(self.fa_poll_loop())

    async def cog_unload(self):
        if self._fa_poll_task:
            self._fa_poll_task.cancel()

    async def notify_owner_of_failures(self):
        """
        Notify me when the FA poller encounters 5 consecutive failures.
        This is to alert me that the FA cookies have expired and need to be refreshed.
        The owner is notified via DM.
        """
        if not OWNER_UID or self.owner_notified:
            return

        try:
            owner = self.bot.get_user(OWNER_UID) or await self.bot.fetch_user(OWNER_UID)
            if owner:
                await owner.send(
                    f"⚠️ **FA Poller Alert** ⚠️\n"
                    f"The FA poller has encountered {self.consecutive_failures} consecutive failures. "
                    f"This may indicate that the FA cookies have expired and need to be refreshed.\n\n"
                    f"Please check the bot logs and update the FA_COOKIE_A and FA_COOKIE_B environment variables."
                )
                self.owner_notified = True
                self.logger.warning(
                    f"Notified owner (ID: {OWNER_UID}) of {self.consecutive_failures} consecutive FA failures"
                )
        except Exception as e:
            self.logger.error(f"Failed to notify owner of FA failures: {e}")

    async def fa_poll_loop(self):
        while True:
            interval_minutes = 5  # fallback default
            try:
                with get_session() as session:
                    fa_subs = (
                        session.query(Subscription)
                        .filter_by(service_type="FurAffinity")
                        .order_by(Subscription.id)
                        .all()
                    )
                    num_subs = len(fa_subs)
                    if num_subs > 0:
                        interval_minutes = max(1, 60 // num_subs)
                    else:
                        interval_minutes = 5
            except Exception as e:
                self.logger.error(f"Error calculating FA poll interval: {e}")
                interval_minutes = 5

            try:
                await self.fa_poll_task_once()
            except Exception as e:
                self.logger.error(
                    f"Unhandled exception in fa_poll_task_once: {e}", exc_info=True
                )
            self.logger.debug(
                f"FA poller cycle complete. Waiting {interval_minutes} minutes to run again."
            )
            await asyncio.sleep(interval_minutes * 60)

    async def fa_poll_task_once(self):
        self.logger.debug("Running FA poller")
        with get_session() as session:
            # ===============================
            # 1. Load and group subscriptions
            # ===============================
            fa_subs = (
                session.query(Subscription).filter_by(service_type="FurAffinity").all()
            )
            self.logger.debug(f"Loaded {len(fa_subs)} FA subscriptions.")
            if not fa_subs:
                return

            from collections import defaultdict

            groups = defaultdict(list)
            for sub in fa_subs:
                groups[sub.search_criteria].append(sub)
            self.logger.debug(f"Grouped into {len(groups)} artist groups.")

            # ============================================
            # 2. Select group to process (oldest last_ran)
            # ============================================
            def group_last_ran(group):
                times = [s.last_ran or 0 for s in group]
                return min(times) if times else 0

            oldest_group = min(groups.values(), key=group_last_ran)
            search_criteria = oldest_group[0].search_criteria
            self.logger.debug(
                f"Selected group for artist '{search_criteria}' with {len(oldest_group)} subscriptions."
            )

            # ====================================
            # 3. Fetch gallery for selected artist
            # ====================================
            cookies = RequestsCookieJar()
            cookies.set("a", FA_COOKIE_A or "")
            cookies.set("b", FA_COOKIE_B or "")
            api = faapi.FAAPI(cookies)
            self.logger.debug(f"Fetching gallery for artist '{search_criteria}'.")
            try:
                gallery, _ = api.gallery(search_criteria, 1)
                # Reset failure counter on successful API call
                if self.consecutive_failures > 0:
                    self.logger.info(
                        f"FA API call successful, resetting failure counter from {self.consecutive_failures}"
                    )
                    self.consecutive_failures = 0
                    self.owner_notified = False
            except Exception as e:
                self.consecutive_failures += 1
                self.logger.warning(
                    f"FA API error for {search_criteria}: {e} (failure #{self.consecutive_failures})"
                )

                # Check if we should notify the owner
                if self.consecutive_failures >= 5:
                    await self.notify_owner_of_failures()

                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after error."
                )
                return
            if not gallery:
                self.logger.warning(f"No gallery for {search_criteria}.")
                now = int(time.time())
                for sub in oldest_group:
                    sub.last_ran = now
                session.commit()
                self.logger.debug(
                    f"Marked {len(oldest_group)} subscriptions as checked after empty gallery."
                )
                return

            latest_posts = gallery[:5]
            ids = [str(post.id) for post in latest_posts]
            now = int(time.time())
            self.logger.debug(f"Latest post IDs for '{search_criteria}': {ids}")

            # =========================================
            # 4. Process each subscription in the group
            # =========================================
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

                # Filter
                positive_filters, negative_filters = parse_filters(sub.filters)
                self.logger.debug(
                    f"Filters for sub {sub.id}: +{positive_filters}, -{negative_filters}"
                )

                # =============================================
                # 5. Post new submissions for this subscription
                # =============================================
                for idx, post_id in enumerate(reversed(new_ids)):
                    try:
                        submission, _ = api.submission(int(post_id))
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to fetch full submission for {post_id}: {e}"
                        )
                        continue
                    tags = set(submission.tags or [])
                    tags = {t.lower() for t in tags}

                    # Add a rating as a special tag when filtering
                    # This is to allow for booru-style filtering
                    # like rating:safe or -rating:explicit
                    rating = getattr(submission, "rating", None)
                    if rating:
                        rating = rating.lower()
                        if rating == "general":
                            tags.add("rating:safe")
                        elif rating in ("mature", "adult"):
                            tags.add("rating:explicit")
                        else:
                            self.logger.warning(
                                f"Unknown rating {rating} in submission {submission.id}."
                            )
                            tags.add("rating:questionable")  # Hard to handle so, idk

                    # Ready to sort
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

                    # Send
                    url = f"https://www.furaffinity.net/view/{post_id}/"
                    use_xfa = False
                    channel = None

                    if sub.is_pm:
                        pass
                    else:
                        channel = await self.bot.fetch_channel(int(sub.channel_id))
                        # Optionally use xfa if channel is nsfw
                        if (
                            channel
                            and hasattr(channel, "is_nsfw")
                            and channel.is_nsfw()
                        ):
                            use_xfa = True
                    if use_xfa:
                        url = f"https://www.xfuraffinity.net/view/{post_id}/"

                    message_content, should_post = format_spoiler_post(
                        post_id, tags, url, channel
                    )
                    if not should_post:
                        self.logger.info(
                            f"Skipping {post_id} due to spoiler tags in non-NSFW channel."
                        )
                        continue
                    url = message_content

                    subtitle = "\n-# Run /manage_following to edit this feed."
                    msg = f"{url}{subtitle}"

                    # Send everything
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
                                        f"Error posting FA update to channel {sub.channel_id}: {e}"
                                    )
                            else:
                                self.logger.error(
                                    f"Channel {sub.channel_id} not found for sub {sub.id}"
                                )
                    except Exception as e:
                        self.logger.error(f"Error posting FA update: {e}")
                if new_ids:
                    sub.last_reported_id = new_ids[0]
                sub.last_ran = now
                self.logger.debug(
                    f"Updated last_reported_id and last_ran for sub {sub.id}"
                )
            # ====================================
            # 6. Commit all updates for this group
            # ====================================
            session.commit()
            self.logger.debug(
                f"Committed updates for {len(oldest_group)} subscriptions in group '{search_criteria}'."
            )


async def setup(bot):
    await bot.add_cog(FA_PollerCog(bot))
