"""A thin, framework-agnostic wrapper around one Bluesky app-password session.

The package has no database layer, persists no session state, and imports
no web framework. The host application decides what (if anything) to store
between calls and when to log in again; this class only ever holds one live
session in memory for as long as the caller keeps the instance around.
"""

from atproto import Client
from atproto_client.exceptions import AtProtocolError, UnauthorizedError

from capsize_bluesky.exceptions import BlueskyAPIError, BlueskyAuthError
from capsize_bluesky.models import ProfileStats

DEFAULT_SERVICE = "https://bsky.social"


class BlueskyAccountClient:
    """One authenticated session for one Bluesky account."""

    def __init__(self, service: str = DEFAULT_SERVICE) -> None:
        """Bind to `service` (a PDS base URL); does not log in yet."""
        self._client = Client(base_url=service)
        self._logged_in = False

    def login(self, handle: str, app_password: str) -> None:
        """Authenticate with an app password (not the account's main password).

        Raises BlueskyAuthError if the handle/app-password pair is rejected,
        or BlueskyAPIError for any other failure (network, rate limit, ...).
        """
        try:
            self._client.login(handle, app_password)
        except UnauthorizedError as exc:
            raise BlueskyAuthError(
                f"Invalid handle or app password for {handle!r}"
            ) from exc
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        self._logged_in = True

    def _require_login(self) -> None:
        if not self._logged_in:
            raise BlueskyAuthError("Not logged in - call login() first")

    def profile_stats(self, actor: str | None = None) -> ProfileStats:
        """Fetch follower/follows/post counts for `actor`, or self."""
        self._require_login()
        target = actor or (self._client.me.did if self._client.me else None)
        if target is None:
            raise BlueskyAuthError("No actor given and no session identity")
        try:
            profile = self._client.get_profile(target)
        except AtProtocolError as exc:
            raise BlueskyAPIError(str(exc)) from exc
        return ProfileStats(
            did=profile.did,
            handle=profile.handle,
            display_name=profile.display_name,
            followers_count=profile.followers_count or 0,
            follows_count=profile.follows_count or 0,
            posts_count=profile.posts_count or 0,
        )

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
