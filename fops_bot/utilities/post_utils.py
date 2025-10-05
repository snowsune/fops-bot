from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class Post:
    """
    Post class

    Generic and works on e6, FA, booru, etc.
    """

    id: str  # The post's ID
    title: str  # The post's title
    rating: str  # The post's rating
    tags: List[str]  # The post's tags
    url: str  # The post's URL
    author: Optional[str] = None  # The post's author
    description: Optional[str] = None  # The post's description
    file_url: Optional[str] = None  # The post's file URL
    preview_url: Optional[str] = None  # The post's preview URL

    def get_display_url(self, use_nsfw_site: bool = False) -> str:
        """
        Get the appropriate URL for display based on NSFW preference.

        (Meant to be overridden)
        """
        return self.url

    def get_filtered_tags(self) -> List[str]:
        """
        Get tags with platform-specific filtering applied.

        (Meant to be overridden)
        """
        return self.tags


class Posts:
    """Generic collection class"""

    def __init__(self, posts: Sequence[Post]):
        self.posts = list(posts)
        self.ids = [post.id for post in posts]

    def __len__(self):
        return len(self.posts)

    def __getitem__(self, index):
        return self.posts[index]

    def get_latest_id(self) -> Optional[str]:
        """Get the ID of the newest post"""
        return self.ids[0] if self.ids else None

    def get_posts_newer_than(self, last_reported_id: str) -> List[Post]:
        """Get all posts newer than the last reported ID"""
        try:
            last_reported_idx = self.ids.index(last_reported_id)
            return self.posts[:last_reported_idx]
        except ValueError:
            # Last reported ID not found
            return []

    def contains_id(self, post_id: str) -> bool:
        """Check if a post ID exists in this collection"""
        return post_id in self.ids

    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get a specific post by ID"""
        try:
            idx = self.ids.index(post_id)
            return self.posts[idx]
        except ValueError:
            return None

    def filter_by_tags(self, required_tags: set, excluded_tags: set) -> List[Post]:
        """Filter posts by required and excluded tags"""
        filtered = []
        for post in self.posts:
            post_tags = set(post.tags)
            if required_tags and not (post_tags & required_tags):
                continue
            if any(tag in post_tags for tag in excluded_tags):
                continue
            filtered.append(post)
        return filtered
