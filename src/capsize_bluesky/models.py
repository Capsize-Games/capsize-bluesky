"""Plain data types returned by capsize_bluesky.

Deliberately not the `atproto` package's own response models: those are
lexicon-shaped and change with the protocol. Callers of this package should
only ever depend on the small stable surface defined here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileStats:
    """The subset of a Bluesky profile this project's dashboards care about."""

    did: str
    handle: str
    display_name: str | None
    followers_count: int
    follows_count: int
    posts_count: int


@dataclass(frozen=True)
class PostRecord:
    """One of this account's own posts, as stored in its repo."""

    uri: str
    cid: str
    text: str
    created_at: str
    # Set when this post is a reply - the AT-URI of the post it replied
    # to, for resolving that surrounding context separately.
    reply_parent_uri: str | None = None


@dataclass(frozen=True)
class RepostRecord:
    """One of this account's own reposts, as stored in its repo."""

    uri: str
    subject_uri: str
    created_at: str
