import os
import logging

SPOILER_TAGS = set(
    t.strip().lower()
    for t in os.getenv("SPOILER_TAGS", "gore bestiality noncon").split()
)


def parse_filters(filter_string):
    """
    Given a filter string (space or comma separated), return (positive_filters, negative_filters) as sets.
    """
    positive_filters = set()
    negative_filters = set()
    if filter_string:
        # Accept both comma and space as separators
        filters = filter_string.replace(",", " ").split()
        for f in filters:
            f = f.strip()
            if not f:
                continue
            if f.startswith("-"):
                negative_filters.add(f[1:].lower())
            else:
                positive_filters.add(f.lower())
    return positive_filters, negative_filters


def format_spoiler_post(post_id, tags, url, channel=None):
    """
    Returns (message_content, should_post). If should_post is False, do not post.
    - If any spoiler tags are present, wraps url in || and prepends CW.
    - If spoiler tags are present and channel is not NSFW, returns (None, False).
    """

    logger = logging.getLogger(__name__)

    tags = {t.lower() for t in tags}
    spoiler_tags_hit = [tag for tag in SPOILER_TAGS if tag in tags]
    spoiler = bool(spoiler_tags_hit)
    logger.debug(
        f"[format_spoiler_post] post_id={post_id}, tags={tags}, spoiler_tags_hit={spoiler_tags_hit}, channel={getattr(channel, 'id', None)}"
    )
    logger.debug(f"[format_spoiler_post] SPOILER_TAGS={SPOILER_TAGS}, tags={tags}")

    if spoiler:
        # Check NSFW
        is_nsfw = None
        if channel is not None:
            is_nsfw = hasattr(channel, "is_nsfw") and channel.is_nsfw()
            logger.info(f"[format_spoiler_post] Channel NSFW status: {is_nsfw}")
            if not is_nsfw:
                logger.info(
                    f"[format_spoiler_post] Skipping post {post_id} due to spoiler tags in non-NSFW channel."
                )
                return (None, False)
        url = f"|| {url} ||"
        cw_title = f"## CW: {', '.join(spoiler_tags_hit)}\n"
        logger.info(
            f"[format_spoiler_post] Posting {post_id} as spoiler with tags {spoiler_tags_hit}."
        )
        return (cw_title + url, True)
    logger.info(f"[format_spoiler_post] Posting {post_id} with no spoiler.")
    return (url, True)
