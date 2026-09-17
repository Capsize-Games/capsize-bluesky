from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from atproto_client.exceptions import BadRequestError, UnauthorizedError

from capsize_bluesky import (
    BlueskyAccountClient,
    BlueskyAPIError,
    BlueskyAuthError,
)

_POST_URI = "at://did:plc:self/app.bsky.feed.post/1"


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
def test_login_returns_profile_stats(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.login.return_value = _fake_profile()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    stats = client.login("alice.bsky.social", "app-password")

    mock_client.login.assert_called_once_with(
        "alice.bsky.social", "app-password"
    )
    assert stats is not None
    assert stats.handle == "alice.bsky.social"
    assert stats.followers_count == 42


@patch("capsize_bluesky.client.Client")
def test_login_returns_none_without_profile(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.login.return_value = None
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    assert client.login("alice.bsky.social", "app-password") is None


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


def _fake_record(
    text: str,
    uri: str,
    cid: str = "cid1",
    reply_parent_uri: str | None = None,
) -> MagicMock:
    record = MagicMock()
    record.uri = uri
    record.cid = cid
    record.value.text = text
    record.value.created_at = "2026-01-01T00:00:00Z"
    if reply_parent_uri is None:
        record.value.reply = None
    else:
        record.value.reply.parent.uri = reply_parent_uri
    return record


def _fake_repost_record(uri: str, subject_uri: str) -> MagicMock:
    record = MagicMock()
    record.uri = uri
    record.value.subject.uri = subject_uri
    record.value.created_at = "2026-01-01T00:00:00Z"
    return record


@patch("capsize_bluesky.client.Client")
def test_list_posts_returns_records_and_cursor(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.list_records.return_value = MagicMock(
        records=[
            _fake_record("hello", "at://did:plc:self/app.bsky.feed.post/1"),
            _fake_record("world", "at://did:plc:self/app.bsky.feed.post/2"),
        ],
        cursor="next-page",
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    posts, cursor = client.list_posts()

    assert [p.text for p in posts] == ["hello", "world"]
    assert cursor == "next-page"
    mock_client.com.atproto.repo.list_records.assert_called_once_with(
        {
            "repo": "did:plc:self",
            "collection": "app.bsky.feed.post",
            "cursor": None,
            "limit": 100,
        }
    )


@patch("capsize_bluesky.client.Client")
def test_list_posts_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.list_posts()


@patch("capsize_bluesky.client.Client")
def test_list_posts_passes_through_cursor(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.com.atproto.repo.list_records.return_value = MagicMock(
        records=[], cursor=None
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    posts, cursor = client.list_posts(
        actor="did:plc:other", cursor="page-2"
    )

    assert posts == []
    assert cursor is None
    mock_client.com.atproto.repo.list_records.assert_called_once_with(
        {
            "repo": "did:plc:other",
            "collection": "app.bsky.feed.post",
            "cursor": "page-2",
            "limit": 100,
        }
    )


@patch("capsize_bluesky.client.Client")
def test_list_posts_wraps_api_errors(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.list_records.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    with pytest.raises(BlueskyAPIError):
        client.list_posts()


@patch("capsize_bluesky.client.Client")
def test_list_posts_captures_reply_parent_uri(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    parent_uri = "at://did:plc:other/app.bsky.feed.post/9"
    mock_client.com.atproto.repo.list_records.return_value = MagicMock(
        records=[
            _fake_record(
                "a reply", _POST_URI, reply_parent_uri=parent_uri
            )
        ],
        cursor=None,
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    posts, _ = client.list_posts()

    assert posts[0].reply_parent_uri == parent_uri


@patch("capsize_bluesky.client.Client")
def test_list_posts_non_reply_has_no_parent_uri(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.list_records.return_value = MagicMock(
        records=[_fake_record("original", _POST_URI)], cursor=None
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    posts, _ = client.list_posts()

    assert posts[0].reply_parent_uri is None


@patch("capsize_bluesky.client.Client")
def test_list_reposts_returns_records_and_cursor(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.list_records.return_value = MagicMock(
        records=[
            _fake_repost_record(
                "at://did:plc:self/app.bsky.feed.repost/1",
                "at://did:plc:other/app.bsky.feed.post/5",
            )
        ],
        cursor="next-page",
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    reposts, cursor = client.list_reposts()

    assert reposts[0].subject_uri == "at://did:plc:other/app.bsky.feed.post/5"
    assert cursor == "next-page"
    mock_client.com.atproto.repo.list_records.assert_called_once_with(
        {
            "repo": "did:plc:self",
            "collection": "app.bsky.feed.repost",
            "cursor": None,
            "limit": 100,
        }
    )


@patch("capsize_bluesky.client.Client")
def test_get_post_returns_record(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    response = MagicMock()
    response.uri = _POST_URI
    response.cid = "cid1"
    response.value.text = "hello"
    response.value.created_at = "2026-01-01T00:00:00Z"
    response.value.reply = None
    mock_client.com.atproto.repo.get_record.return_value = response
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    post = client.get_post(_POST_URI)

    assert post is not None
    assert post.text == "hello"
    mock_client.com.atproto.repo.get_record.assert_called_once_with(
        {
            "repo": "did:plc:self",
            "collection": "app.bsky.feed.post",
            "rkey": "1",
        }
    )


@patch("capsize_bluesky.client.Client")
def test_get_post_returns_none_when_unavailable(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.com.atproto.repo.get_record.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    assert client.get_post(_POST_URI) is None


@patch("capsize_bluesky.client.Client")
def test_get_post_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.get_post(_POST_URI)


@patch("capsize_bluesky.client.Client")
def test_delete_post_calls_delete_record(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client.delete_post(_POST_URI)

    mock_client.com.atproto.repo.delete_record.assert_called_once_with(
        {
            "repo": "did:plc:self",
            "collection": "app.bsky.feed.post",
            "rkey": "1",
        }
    )


@patch("capsize_bluesky.client.Client")
def test_delete_post_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.delete_post(_POST_URI)


@patch("capsize_bluesky.client.Client")
def test_delete_post_wraps_api_errors(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.com.atproto.repo.delete_record.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    with pytest.raises(BlueskyAPIError):
        client.delete_post(_POST_URI)


@patch("capsize_bluesky.client.Client")
def test_resolve_handle(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.resolve_handle.return_value = MagicMock(did="did:plc:abc123")
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    assert client.resolve_handle("alice.bsky.social") == "did:plc:abc123"


@patch("capsize_bluesky.client.Client")
def test_update_profile_sets_description(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.get_record.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client.update_profile(description="new bio")

    mock_client.com.atproto.repo.put_record.assert_called_once()
    call_args = mock_client.com.atproto.repo.put_record.call_args[0][0]
    assert call_args["repo"] == "did:plc:self"
    assert call_args["collection"] == "app.bsky.actor.profile"
    assert call_args["rkey"] == "self"
    assert call_args["record"].description == "new bio"


@patch("capsize_bluesky.client.Client")
def test_update_profile_preserves_existing_fields(
    mock_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.get_record.return_value = MagicMock(
        value={"description": "old bio", "display_name": "Old Name"}
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client.update_profile(description="new bio")

    call_args = mock_client.com.atproto.repo.put_record.call_args[0][0]
    assert call_args["record"].description == "new bio"
    assert call_args["record"].display_name == "Old Name"


@patch("capsize_bluesky.client.Client")
def test_update_profile_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.update_profile(description="new bio")


@patch("capsize_bluesky.client.Client")
def test_update_profile_wraps_api_errors(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.me.did = "did:plc:self"
    mock_client.com.atproto.repo.get_record.side_effect = BadRequestError()
    mock_client.com.atproto.repo.put_record.side_effect = BadRequestError()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    with pytest.raises(BlueskyAPIError):
        client.update_profile(description="new bio")


@patch("capsize_bluesky.client.Client")
def test_update_handle_sends_new_handle(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    client.update_handle("alice.example.com")

    mock_client.com.atproto.identity.update_handle.assert_called_once_with(
        {"handle": "alice.example.com"}
    )


@patch("capsize_bluesky.client.Client")
def test_update_handle_requires_login(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    client = BlueskyAccountClient()
    with pytest.raises(BlueskyAuthError):
        client.update_handle("alice.example.com")


@patch("capsize_bluesky.client.Client")
def test_update_handle_wraps_api_errors(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.com.atproto.identity.update_handle.side_effect = (
        BadRequestError()
    )
    mock_client_cls.return_value = mock_client

    client = BlueskyAccountClient()
    client.login("alice.bsky.social", "app-password")
    with pytest.raises(BlueskyAPIError):
        client.update_handle("alice.example.com")
