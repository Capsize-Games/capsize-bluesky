"""Post/repost read, delete, and create methods for `BlueskyAccountClient`.

Split out of `client.py` to keep that file under this project's own
250-line limit - these methods are all about the account's own post
history, a distinct concern from session/profile management.
"""

from atproto_client.exceptions import AtProtocolError
from atproto_client.models.com.atproto.repo.get_record import (
    Response as GetRecordResponse,
)
from atproto_client.models.com.atproto.repo.list_records import (
    Record as ListRecordsRecord,
)

from capsize_bluesky._session import _SessionProtocol
from capsize_bluesky.exceptions import BlueskyAPIError
from capsize_bluesky.models import PostRecord, RepostRecord

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


class _ContentMixin:
    """Reading, posting, and deleting this account's own repo records."""

    def list_posts(
        self: _SessionProtocol,
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
        self: _SessionProtocol,
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

    def get_post(self: _SessionProtocol, uri: str) -> PostRecord | None:
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

    def delete_post(self: _SessionProtocol, uri: str) -> None:
        """Permanently delete one of this account's own posts."""
        self._require_login()
        did, collection, rkey = _parse_at_uri(uri)
        try:
            self._client.com.atproto.repo.delete_record(
                {"repo": did, "collection": collection, "rkey": rkey}
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc

    def create_post(self: _SessionProtocol, text: str) -> str:
        """Publish a text post. Returns the created record's AT URI."""
        self._require_login()
        try:
            result = self._client.send_post(text)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return str(result.uri)
