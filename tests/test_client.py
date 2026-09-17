from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from atproto_client.exceptions import BadRequestError, UnauthorizedError

from capsize_bluesky import (
    BlueskyAccountClient,
    BlueskyAPIError,
    BlueskyAuthError,
)


def _fake_profile(**overrides: object) -> MagicMock:
    profile = MagicMock()
    profile.did = overrides.get("did", "did:plc:abc123")
    profile.handle = overrides.get("handle", "alice.bsky.social")
    profile.display_name = overrides.get("display_name", "Alice")
    profile.followers_count = overrides.get("followers_count", 42)
    profile.follows_count = overrides.get("follows_count", 7)
    profile.posts_count = overrides.get("posts_count", 100)
    return profile


@patch("capsize_bluesky.client.Client")
def test_login_success(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client._client.login.assert_called_once_with(
        "alice.bsky.social", "app-password"
    )


@patch("capsize_bluesky.client.Client")
def test_login_bad_credentials_raises_auth_error(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.login.side_effect = UnauthorizedError("bad creds")
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.login("alice.bsky.social", "wrong-password")


@patch("capsize_bluesky.client.Client")
def test_login_other_failure_raises_api_error(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.login.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAPIError):
        client.login("alice.bsky.social", "app-password")


@patch("capsize_bluesky.client.Client")
def test_profile_stats_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.profile_stats()


@patch("capsize_bluesky.client.Client")
def test_profile_stats_returns_counts(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.get_profile.return_value = _fake_profile()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    stats = client.profile_stats("alice.bsky.social")

    assert stats.handle == "alice.bsky.social"
    assert stats.followers_count == 42
    assert stats.follows_count == 7
    assert stats.posts_count == 100
    mock_client.get_profile.assert_called_once_with("alice.bsky.social")


@patch("capsize_bluesky.client.Client")
def test_profile_stats_defaults_to_own_did(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.get_profile.return_value = _fake_profile()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client.profile_stats()

    mock_client.get_profile.assert_called_once_with("did:plc:self")


@patch("capsize_bluesky.client.Client")
def test_create_post_returns_uri(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.send_post.return_value = MagicMock(uri="at://did:plc:abc/app.bsky.feed.post/1")
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    uri = client.create_post("hello world")

    assert uri == "at://did:plc:abc/app.bsky.feed.post/1"
    mock_client.send_post.assert_called_once_with("hello world")


@patch("capsize_bluesky.client.Client")
def test_create_post_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.create_post("hello world")


@patch("capsize_bluesky.client.Client")
def test_resolve_handle(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.resolve_handle.return_value = MagicMock(did="did:plc:abc123")
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    assert client.resolve_handle("alice.bsky.social") == "did:plc:abc123"
