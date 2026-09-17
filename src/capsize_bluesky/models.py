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
