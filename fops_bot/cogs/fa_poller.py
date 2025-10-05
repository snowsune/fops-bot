import os
import faapi
import discord
import logging
import time
from dataclasses import dataclass
from typing import List

from fops_bot.models import get_session, Subscription
from requests.cookies import RequestsCookieJar
from cogs.subscribe_resources.base_poller import BasePollerCog
from utilities.post_utils import Post, Posts

FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")
OWNER_UID = int(os.getenv("OWNER_UID", "0"))


@dataclass
class FAPost(Post):
    """FurAffinity-specific post implementation"""

    xfa_url: str = ""

    def get_display_url(self, use_nsfw_site: bool = False) -> str:
        """Return XFA URL if NSFW site is preferred"""
        return self.xfa_url if use_nsfw_site else self.url

    @classmethod
    def from_api_submission(cls, submission, post_id: str):
        """Create FAPost from FA API submission"""
        tags = list(submission.tags or [])
        rating = getattr(submission, "rating", "unknown").lower()

        # Normalize rating tags
        if rating == "general":
            tags.append("rating:safe")
        elif rating in ("mature", "adult"):
            tags.append("rating:explicit")
        else:
            tags.append("rating:questionable")

        return cls(
            id=post_id,
            title=getattr(submission, "title", "Untitled"),
            rating=rating,
            tags=[t.lower() for t in tags],
            url=f"https://www.furaffinity.net/view/{post_id}/",
            xfa_url=f"https://www.xfuraffinity.net/view/{post_id}/",
            author=getattr(submission, "author", None),
            description=getattr(submission, "description", None),
        )


class FAPosts(Posts):
    """FurAffinity-specific posts collection"""

    def __init__(self, posts: List[FAPost]):
        super().__init__(posts)
        if not all(isinstance(post, FAPost) for post in posts):
            raise ValueError("All posts must be FAPost instances")


class FA_PollerCog(BasePollerCog):
    """FurAffinity poller implementation"""

    def __init__(self, bot):
        super().__init__(bot, "FurAffinity")

    async def fetch_latest_posts(self, search_criteria: str) -> Posts:
        """Fetch latest posts from FurAffinity for the given search criteria"""
        cookies = RequestsCookieJar()
        cookies.set("a", FA_COOKIE_A or "")
        cookies.set("b", FA_COOKIE_B or "")
        api = faapi.FAAPI(cookies)

        self.logger.debug(f"Fetching gallery for artist '{search_criteria}'.")
        gallery, _ = api.gallery(search_criteria, 1)

        if not gallery:
            self.logger.warning(f"No gallery for {search_criteria}.")
            return FAPosts([])

        # Get post IDs from gallery and fetch full submissions
        latest_post_ids = [str(post.id) for post in gallery[:5]]

        # Fetch full submissions for each post ID
        fa_posts = []
        for post_id in latest_post_ids:
            try:
                submission, _ = api.submission(int(post_id))
                fa_post = FAPost.from_api_submission(submission, post_id)
                fa_posts.append(fa_post)
            except Exception as e:
                self.logger.warning(
                    f"Failed to fetch full submission for {post_id}: {e}"
                )
                continue

        fa_posts_collection = FAPosts(fa_posts)

        self.logger.debug(
            f"Latest post IDs for '{search_criteria}': {fa_posts_collection.ids}"
        )
        return fa_posts_collection

    async def notify_owner_of_failures(self, search_criteria: str, error: Exception):
        """Notify me when FA poller encounters 5 consecutive failures"""
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


async def setup(bot):
    await bot.add_cog(FA_PollerCog(bot))
