"""Exceptions raised by capsize_bluesky.

These wrap whatever the underlying transport (currently the `atproto`
package) raises, so callers never need to import or catch that package's
own exception types directly.
"""


class BlueskyError(Exception):
    """Base class for all errors raised by this package."""


class BlueskyAuthError(BlueskyError):
    """The handle/app-password pair was rejected by the PDS."""


class BlueskyAPIError(BlueskyError):
    """Any other AT Protocol request failure (network, rate limit, etc.)."""
