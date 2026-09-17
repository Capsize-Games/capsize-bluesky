"""Profile and handle mutation methods for `BlueskyAccountClient`.

Split out of `client.py` to keep that file under this project's own
250-line limit - these methods are all about mutating this account's
own identity record, a distinct concern from reading/posting content.
"""

from atproto import models
from atproto_client.exceptions import AtProtocolError
from atproto_client.models.blob_ref import BlobRef

from capsize_bluesky._session import _SessionProtocol
from capsize_bluesky.exceptions import BlueskyAPIError

_PROFILE_COLLECTION = "app.bsky.actor.profile"
_PROFILE_FIELDS = ("description", "display_name", "avatar", "banner")


class _ProfileMixin(_SessionProtocol):
    """Handle switching and bio/display-name/avatar/banner updates.

    Inherits `_SessionProtocol` (not just typing `self` against it per
    method) so sibling mixin methods - `update_profile` calling its own
    `_upload_image`/`_write_profile_record` - type-check too, not just
    the session attributes themselves.
    """

    def update_handle(self, handle: str) -> None:
        """Switch this account's own handle (e.g. to a custom domain).

        The caller is responsible for having already published the
        domain-verification DNS record this account's PDS requires -
        this only calls the AT Protocol identity update itself, it
        doesn't check or wait for DNS.
        """
        self._require_login()
        try:
            self._client.com.atproto.identity.update_handle({"handle": handle})
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc

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
                    "collection": _PROFILE_COLLECTION,
                    "rkey": "self",
                }
            )
        except AtProtocolError:
            return {}
        value = existing.value
        if isinstance(value, dict):
            return dict(value)
        return {
            f: getattr(value, f, None)
            for f in _PROFILE_FIELDS
            if hasattr(value, f)
        }

    def _upload_image(self, data: bytes) -> BlobRef:
        """Upload raw image bytes, for use as an avatar/banner blob ref."""
        try:
            response = self._client.upload_blob(data)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return response.blob

    def _write_profile_record(self, did: str, record: object) -> None:
        try:
            self._client.com.atproto.repo.put_record(
                {
                    "repo": did,
                    "collection": _PROFILE_COLLECTION,
                    "rkey": "self",
                    "record": record,
                }
            )
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc

    def update_profile(
        self,
        description: str | None = None,
        display_name: str | None = None,
        avatar: bytes | None = None,
        banner: bytes | None = None,
    ) -> None:
        """Update this account's own bio, display name, avatar, banner.

        Reads the existing profile record first and only overwrites
        the fields given here, so an untouched field isn't accidentally
        cleared by a partial update. `avatar`/`banner`, if given, are
        raw image bytes - uploaded as blobs before being attached.
        """
        self._require_login()
        did = self._resolve_target(None)
        fields = self._existing_profile_fields(did)
        if description is not None:
            fields["description"] = description
        if display_name is not None:
            fields["display_name"] = display_name
        if avatar is not None:
            fields["avatar"] = self._upload_image(avatar)
        if banner is not None:
            fields["banner"] = self._upload_image(banner)
        record = models.AppBskyActorProfile.Record(
            **{k: v for k, v in fields.items() if v is not None}
        )
        self._write_profile_record(did, record)
