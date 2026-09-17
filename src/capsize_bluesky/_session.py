"""The session state `_ContentMixin`/`_ProfileMixin` methods rely on.

A `Protocol`, not the concrete `BlueskyAccountClient` - a mixin's `self`
is never a supertype of the class it will eventually be mixed into, so
typing each mixin method against this structural shape (rather than the
concrete class) is what lets mypy check them independently.
"""

from typing import Protocol

from atproto import Client


class _SessionProtocol(Protocol):
    _client: Client

    def _require_login(self) -> None: ...

    def _resolve_target(self, actor: str | None) -> str: ...
