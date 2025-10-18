import os
import discord
import logging
import requests
from dataclasses import dataclass
from typing import List

from fops_bot.models import get_session, Subscription
from cogs.subscribe_resources.base_poller import BasePollerCog
from utilities.post_utils import Post, Posts

# e621 API configuration
E621_URL = "https://e621.net"
E621_USER_AGENT = os.getenv("E621_USER_AGENT", "FopsBot/1.0 (by snowsune on e621)")
E621_USERNAME = os.getenv("E621_USERNAME")
E621_API_KEY = os.getenv("E621_API_KEY")


@dataclass
class E621Post(Post):
    """e621-specific post implementation"""

    def get_display_url(self, use_nsfw_site: bool = False) -> str:
        return self.url

    @classmethod
    def from_api_post(cls, post_data: dict, post_id: str):
        tags = set(post_data.get("tag_string", "").split())
        tags = {t.lower() for t in tags}

        rating = post_data.get("rating", "unknown").lower()
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
            title=f"e621 Post #{post_id}",
            rating=rating,
            tags=list(tags),
            url=f"{E621_URL}/posts/{post_id}",
            author=post_data.get("uploader", None),
            description=post_data.get("description", None),
        )


class E621Posts(Posts):
    """e621-specific posts collection"""

    def __init__(self, posts: List[E621Post]):
        super().__init__(posts)
        if not all(isinstance(post, E621Post) for post in posts):
            raise ValueError("All posts must be E621Post instances")


class E621PollerCog(BasePollerCog):
    """e621 poller implementation"""

    def __init__(self, bot):
        super().__init__(bot, "e621")

    async def fetch_latest_posts(self, search_criteria: str) -> Posts:
        """Fetch latest posts from e621 for the given search criteria"""
        try:
            params = {"tags": search_criteria, "limit": 5}
            if E621_USERNAME and E621_API_KEY:
                params.update({"login": E621_USERNAME, "api_key": E621_API_KEY})

            response = requests.get(
                f"{E621_URL}/posts.json",
                params=params,
                headers={"User-Agent": E621_USER_AGENT},
            )

            if response.status_code != 200:
                return E621Posts([])

            posts_data = response.json()

            # Handle wrapped responses
            if isinstance(posts_data, dict):
                if "error" in posts_data or "message" in posts_data:
                    return E621Posts([])
                posts_data = posts_data.get("posts", [])

            if not isinstance(posts_data, list):
                return E621Posts([])

            e621_posts = []
            for post_data in posts_data:
                if isinstance(post_data, dict) and post_data.get("id"):
                    e621_posts.append(
                        E621Post.from_api_post(post_data, str(post_data["id"]))
                    )

            return E621Posts(e621_posts)

        except Exception:
            return E621Posts([])

    async def notify_owner_of_failures(self, search_criteria: str, error: Exception):
        """Notify the owner when e621 poller encounters 5 consecutive failures"""
        self.logger.error(f"e621 poller failure for {search_criteria}: {error}")


async def setup(bot):
    await bot.add_cog(E621PollerCog(bot))
