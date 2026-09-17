"""A thin, framework-agnostic wrapper around one Bluesky app-password session.

The package has no database layer, persists no session state, and imports
no web framework. The host application decides what (if anything) to store
between calls and when to log in again; this class only ever holds one live
session in memory for as long as the caller keeps the instance around.
"""

from atproto import Client
from atproto_client.exceptions import AtProtocolError, UnauthorizedError
from atproto_client.models.app.bsky.actor.defs import ProfileViewDetailed
from atproto_client.models.com.atproto.repo.list_records import (
    Record as ListRecordsRecord,
)

from capsize_bluesky.exceptions import BlueskyAPIError, BlueskyAuthError
from capsize_bluesky.models import PostRecord, ProfileStats

DEFAULT_SERVICE = "https://bsky.social"
_POSTS_COLLECTION = "app.bsky.feed.post"
_LIST_PAGE_SIZE = 100


def _authenticate(
    client: Client, handle: str, app_password: str
) -> ProfileViewDetailed | None:
    """Log `client` in, translating atproto's exceptions on the way."""
    try:
        return client.login(handle, app_password)
    except UnauthorizedError as exc:
        raise BlueskyAuthError(
            f"Invalid handle or app password for {handle!r}"
        ) from exc
    except AtProtocolError as exc:
        raise BlueskyAPIError(str(exc)) from exc


def _to_profile_stats(profile: ProfileViewDetailed) -> ProfileStats:
    return ProfileStats(
        did=profile.did,
        handle=profile.handle,
        display_name=profile.display_name,
        followers_count=profile.followers_count or 0,
        follows_count=profile.follows_count or 0,
        posts_count=profile.posts_count or 0,
    )


def _to_post_record(record: ListRecordsRecord) -> PostRecord:
    value = record.value
    return PostRecord(
        uri=str(record.uri),
        cid=str(record.cid),
        text=str(value.text),
        created_at=str(value.created_at),
    )


class BlueskyAccountClient:
    """One authenticated session for one Bluesky account."""

    def __init__(self, service: str = DEFAULT_SERVICE) -> None:
        """Bind to `service` (a PDS base URL); does not log in yet."""
        self._client = Client(base_url=service)
        self._logged_in = False

    def login(
        self, handle: str, app_password: str
    ) -> ProfileStats | None:
        """Authenticate with an app password, not the account's password.

        Returns the account's own profile stats, included in the PDS's
        login response by default — skips a second `profile_stats()`
        round-trip. Raises `BlueskyAuthError`/`BlueskyAPIError`; see
        `_authenticate`.
        """
        profile = _authenticate(self._client, handle, app_password)
        self._logged_in = True
        return _to_profile_stats(profile) if profile else None

    def _require_login(self) -> None:
        if not self._logged_in:
            raise BlueskyAuthError("Not logged in - call login() first")

    def _resolve_target(self, actor: str | None) -> str:
        target = actor or (self._client.me.did if self._client.me else None)
        if target is None:
            raise BlueskyAuthError("No actor given and no session identity")
        return target

    def profile_stats(self, actor: str | None = None) -> ProfileStats:
        """Fetch follower/follows/post counts for `actor`, or self."""
        self._require_login()
        target = self._resolve_target(actor)
        try:
            profile = self._client.get_profile(target)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return _to_profile_stats(profile)

    def list_posts(
        self,
        actor: str | None = None,
        cursor: str | None = None,
        limit: int = _LIST_PAGE_SIZE,
    ) -> tuple[list[PostRecord], str | None]:
        """Return one page of `actor`'s (or self's) own post records.

        Reads directly from the account's repo (`listRecords`), not the
        `getAuthorFeed` view - every post it ever made, in creation
        order, with no feed-algorithm filtering in the way.
        """
        self._require_login()
        target = self._resolve_target(actor)
        try:
            response = self._client.com.atproto.repo.list_records(
                {
                    "repo": target,
                    "collection": _POSTS_COLLECTION,
                    "cursor": cursor,
                    "limit": limit,
                }
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        records = [_to_post_record(r) for r in response.records]
        return records, response.cursor

    def create_post(self, text: str) -> str:
        """Publish a text post. Returns the created record's AT URI."""
        self._require_login()
        try:
            result = self._client.send_post(text)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return str(result.uri)

    def resolve_handle(self, handle: str) -> str:
        """Resolve a handle (e.g. `alice.bsky.social`) to its DID."""
        try:
            response = self._client.resolve_handle(handle)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return str(response.did)
