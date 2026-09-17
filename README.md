# capsize-bluesky

A small Bluesky (AT Protocol) client for app-password login, profile stats,
and posting — built on the [`atproto`](https://pypi.org/project/atproto/)
package, with no database layer, no session persistence, and no web
framework assumptions.

```bash
pip install capsize-bluesky
```

## What it does not assume

The package holds one session in memory for as long as you keep the client
instance around. It does not read environment variables, does not store
credentials anywhere, and does not know about your database or web
framework. The host application decides what (if anything) to persist
between calls. That is the same boundary
[`capsize-auth`](https://github.com/capsize-games/capsize-auth) draws for
authentication primitives, applied here to a third-party API client.

## Usage

```python
from capsize_bluesky import BlueskyAccountClient, BlueskyAuthError

client = BlueskyAccountClient()  # defaults to https://bsky.social

try:
    stats = client.login("alice.bsky.social", app_password)
except BlueskyAuthError:
    ...  # bad handle / app password

# login() already returns profile stats from the PDS's login response;
# call profile_stats() again later only when you need a fresh count.
print(stats.followers_count, stats.follows_count, stats.posts_count)

client.create_post("Hello, Bluesky!")
```

Use an **app password** (Settings → Privacy & Security → App Passwords on
bsky.app), never the account's main password.

## Errors

`login`, `profile_stats`, `create_post`, and `resolve_handle` raise:

- `BlueskyAuthError` — bad handle/app-password, or calling a method that
  needs a session before `login()` succeeded.
- `BlueskyAPIError` — any other AT Protocol failure (network, rate limit,
  malformed request, ...).

Both subclass `BlueskyError`, so callers that don't care about the
distinction can catch just that.

## Custom PDS

```python
client = BlueskyAccountClient(service="https://my-pds.example.com")
```
