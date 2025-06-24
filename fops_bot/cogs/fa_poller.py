import os
import faapi
import discord
import logging

from discord.ext import commands, tasks
from fops_bot.models import get_session, Subscription, KeyValueStore
from datetime import datetime, timezone
from requests.cookies import RequestsCookieJar

FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")


class FA_PollerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

        self.fa_poll_task.start()

    def cog_unload(self):
        self.fa_poll_task.cancel()

    @tasks.loop(minutes=5)
    async def fa_poll_task(self):
        self.logger.debug("Running FA poller")

        with get_session() as session:
            fa_subs = (
                session.query(Subscription)
                .filter_by(service_type="FurAffinity")
                .order_by(Subscription.id)
                .all()
            )
            if not fa_subs:
                return

            # Get last processed index from KeyValueStore
            kv = session.get(KeyValueStore, "fa_poller_index")
            last_index = int(kv.value) if kv and kv.value else 0
            sub = fa_subs[last_index % len(fa_subs)]

            # Prepare FA API
            cookies = RequestsCookieJar()
            cookies.set("a", FA_COOKIE_A or "")
            cookies.set("b", FA_COOKIE_B or "")
            api = faapi.FAAPI(cookies)
            try:
                gallery, _ = api.gallery(sub.search_criteria, 1)
            except Exception as e:
                self.logger.warning(f"FA API error for {sub.search_criteria}: {e}")
                return
            if not gallery:
                self.logger.warning(f"No gallery for {sub.search_criteria}.")
                return

            latest_posts = gallery[:5]
            ids = [str(post.id) for post in latest_posts]
            if sub.last_reported_id in ids:
                new_ids = ids[: ids.index(sub.last_reported_id)]
            else:
                new_ids = ids

            # Parse filters for this subscription (space-separated)
            positive_filters = set()
            negative_filters = set()
            if sub.filters:
                for f in sub.filters.split():
                    f = f.strip()
                    if not f:
                        continue
                    if f.startswith("-"):
                        negative_filters.add(f[1:].lower())
                    else:
                        positive_filters.add(f.lower())

            # Post new submissions in order (oldest first)
            for idx, post_id in enumerate(reversed(new_ids)):
                # ---
                # 1. Fetch the full Submission object (needed for tags)
                # ---
                try:
                    submission, _ = api.submission(int(post_id))
                except Exception as e:
                    self.logger.warning(
                        f"Failed to fetch full submission for {post_id}: {e}"
                    )
                    continue

                # ---
                # 2. Extract tags and normalize
                # ---
                tags = set(submission.tags or [])
                tags = {t.lower() for t in tags}
                self.logger.debug(f"Post {post_id} tags: {tags}")

                # ---
                # 3. Apply positive/negative filter logic
                # ---
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

                # ---
                # 4. Determine which link to use (NSFW logic)
                # ---
                url = f"https://www.furaffinity.net/view/{post_id}/"
                use_xfa = False
                channel = None
                if sub.is_pm:
                    pass
                else:
                    channel = self.bot.get_channel(sub.channel_id)
                    if channel and hasattr(channel, "is_nsfw") and channel.is_nsfw():
                        use_xfa = True
                if use_xfa:
                    url = f"https://www.xfuraffinity.net/view/{post_id}/"
                subtitle = "\n-# Run /manage_following to edit this feed."
                msg = f"{url}{subtitle}"

                # ---
                # 5. Post the message to the correct destination
                # ---
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
                            await channel.send(msg)
                except Exception as e:
                    self.logger.error(f"Error posting FA update: {e}")
            # Always update last_reported_id to the newest scanned post
            if new_ids:
                sub.last_reported_id = new_ids[0]
                session.commit()

            # Update poller index
            next_index = (last_index + 1) % len(fa_subs)
            if kv:
                kv.value = str(next_index)
            else:
                session.add(KeyValueStore(key="fa_poller_index", value=str(next_index)))
            session.commit()


async def setup(bot):
    await bot.add_cog(FA_PollerCog(bot))
