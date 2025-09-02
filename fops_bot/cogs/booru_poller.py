import os
import discord
import logging
from dataclasses import dataclass
from typing import List

from fops_bot.models import get_session, Subscription
from cogs.subscribe_resources.base_poller import BasePollerCog
from utilities.post_utils import Post, Posts
from fops_bot.scripts.Booru_Scripts import booru_utils

BOORU_URL = os.getenv("BOORU_URL", "https://booru.kitsunehosting.net")
BOORU_API_KEY = os.getenv("BOORU_KEY")
BOORU_USERNAME = os.getenv("BOORU_USER")


@dataclass
class BooruPost(Post):
    """Booru-specific post implementation"""

    def get_display_url(self, use_nsfw_site: bool = False) -> str:
        """Return the same URL for booru posts"""
        return self.url

    @classmethod
    def from_api_post(cls, post_data: dict, post_id: str):
        """Create BooruPost from booru API post data"""
        tags = set(post_data.get("tag_string", "").split())
        tags = {t.lower() for t in tags}

        rating = post_data.get("rating", "unknown")
        if rating:
            rating = rating.lower()
            if rating == "s":
                tags.add("rating:safe")
            elif rating == "e":
                tags.add("rating:explicit")
            elif rating == "q":
                tags.add("rating:questionable")
            else:
                tags.add("rating:unknown")

        return cls(
            id=post_id,
            title=post_data.get("title", "Untitled"),
            rating=rating,
            tags=list(tags),
            url=f"{BOORU_URL}/posts/{post_id}",
            author=post_data.get("uploader", None),
            description=post_data.get("description", None),
        )


class BooruPosts(Posts):
    """Booru-specific posts collection"""

    def __init__(self, posts: List[BooruPost]):
        super().__init__(posts)
        if not all(isinstance(post, BooruPost) for post in posts):
            raise ValueError("All posts must be BooruPost instances")


class BooruPollerCog(BasePollerCog):
    """Booru poller implementation"""

    def __init__(self, bot):
        super().__init__(bot, "BixiBooru")

    async def fetch_latest_posts(self, search_criteria: str) -> Posts:
        """Fetch latest posts from Booru for the given search criteria"""
        self.logger.debug(f"Fetching posts for tag '{search_criteria}'.")

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
            return BooruPosts([])

        if not posts:
            self.logger.warning(f"No posts for {search_criteria}.")
            return BooruPosts([])

        # Convert API posts to BooruPosts collection
        booru_posts = []
        for post_data in posts:
            post_id = str(post_data.get("id"))
            if post_id:
                booru_post = BooruPost.from_api_post(post_data, post_id)
                booru_posts.append(booru_post)

        booru_posts_collection = BooruPosts(booru_posts)
        self.logger.debug(
            f"Latest post IDs for '{search_criteria}': {booru_posts_collection.ids}"
        )
        return booru_posts_collection

    async def notify_owner_of_failures(self, search_criteria: str, error: Exception):
        """Notify the owner when Booru poller encounters 5 consecutive failures"""
        # For now, just log the error since Booru doesn't have the same cookie issues as FA
        self.logger.error(f"Booru poller failure for {search_criteria}: {error}")


async def setup(bot):
    await bot.add_cog(BooruPollerCog(bot))
