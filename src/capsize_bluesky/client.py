"""A thin, framework-agnostic wrapper around one Bluesky app-password session.

The package has no database layer, persists no session state, and imports
no web framework. The host application decides what (if anything) to store
between calls and when to log in again; this class only ever holds one live
session in memory for as long as the caller keeps the instance around.
"""

from atproto import Client, models
from atproto_client.exceptions import AtProtocolError, UnauthorizedError
from atproto_client.models.app.bsky.actor.defs import ProfileViewDetailed
from atproto_client.models.com.atproto.repo.get_record import (
    Response as GetRecordResponse,
)
from atproto_client.models.com.atproto.repo.list_records import (
    Record as ListRecordsRecord,
)

from capsize_bluesky.exceptions import BlueskyAPIError, BlueskyAuthError
from capsize_bluesky.models import PostRecord, ProfileStats, RepostRecord

DEFAULT_SERVICE = "https://bsky.social"
_POSTS_COLLECTION = "app.bsky.feed.post"
_REPOSTS_COLLECTION = "app.bsky.feed.repost"
_LIST_PAGE_SIZE = 100


def _parse_at_uri(uri: str) -> tuple[str, str, str]:
    """Split `at://<did>/<collection>/<rkey>` into its three parts."""
    parts = uri.removeprefix("at://").split("/")
    if len(parts) != 3 or not all(parts):
        raise BlueskyAPIError(f"Malformed AT-URI: {uri!r}")
    did, collection, rkey = parts
    return did, collection, rkey


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


def _reply_parent_uri(value: object) -> str | None:
    reply = getattr(value, "reply", None)
    if reply is None:
        return None
    return str(reply.parent.uri)


def _to_post_record(
    record: ListRecordsRecord | GetRecordResponse,
) -> PostRecord:
    value = record.value
    return PostRecord(
        uri=str(record.uri),
        cid=str(record.cid) if record.cid else "",
        text=str(value.text),
        created_at=str(value.created_at),
        reply_parent_uri=_reply_parent_uri(value),
    )


def _to_repost_record(record: ListRecordsRecord) -> RepostRecord:
    value = record.value
    return RepostRecord(
        uri=str(record.uri),
        subject_uri=str(value.subject.uri),
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

    def list_reposts(
        self,
        actor: str | None = None,
        cursor: str | None = None,
        limit: int = _LIST_PAGE_SIZE,
    ) -> tuple[list[RepostRecord], str | None]:
        """Return one page of `actor`'s (or self's) own reposts."""
        self._require_login()
        target = self._resolve_target(actor)
        try:
            response = self._client.com.atproto.repo.list_records(
                {
                    "repo": target,
                    "collection": _REPOSTS_COLLECTION,
                    "cursor": cursor,
                    "limit": limit,
                }
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        records = [_to_repost_record(r) for r in response.records]
        return records, response.cursor

    def get_post(self, uri: str) -> PostRecord | None:
        """Fetch a single post by its AT-URI, or `None` if unavailable.

        Best-effort: a reply's parent may since have been deleted, or
        belong to a repo this session can't reach - either case
        returns `None` rather than raising, since this is for optional
        surrounding context, not a required lookup.
        """
        self._require_login()
        did, collection, rkey = _parse_at_uri(uri)
        try:
            response = self._client.com.atproto.repo.get_record(
                {"repo": did, "collection": collection, "rkey": rkey}
            )
        except AtProtocolError:
            return None
        return _to_post_record(response)

    def delete_post(self, uri: str) -> None:
        """Permanently delete one of this account's own posts."""
        self._require_login()
        did, collection, rkey = _parse_at_uri(uri)
        try:
            self._client.com.atproto.repo.delete_record(
                {"repo": did, "collection": collection, "rkey": rkey}
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc

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

    def _existing_profile_fields(self, did: str) -> dict[str, object]:
        """Return the existing profile record's fields as a plain dict.

        `get_record`'s `.value` is untyped (the SDK returns it as
        `Any`, not a parsed `AppBskyActorProfile.Record`) - reading it
        defensively via both attribute and dict-style access covers
        either shape rather than assuming one.
        """
        try:
            existing = self._client.com.atproto.repo.get_record(
                {
                    "repo": did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                }
            )
        except AtProtocolError:
            return {}
        value = existing.value
        if isinstance(value, dict):
            return dict(value)
        fields = ("description", "display_name", "avatar", "banner")
        return {
            f: getattr(value, f, None) for f in fields if hasattr(value, f)
        }

    def update_profile(
        self,
        description: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Update this account's own bio text and/or display name.

        Reads the existing profile record first and only overwrites
        the fields given here, so an existing avatar/banner (this
        package doesn't touch image blobs) or any other field isn't
        accidentally cleared by a partial update.
        """
        self._require_login()
        did = self._resolve_target(None)
        fields = self._existing_profile_fields(did)
        if description is not None:
            fields["description"] = description
        if display_name is not None:
            fields["display_name"] = display_name
        record = models.AppBskyActorProfile.Record(
            **{k: v for k, v in fields.items() if v is not None}
        )
        try:
            self._client.com.atproto.repo.put_record(
                {
                    "repo": did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                    "record": record,
                }
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
