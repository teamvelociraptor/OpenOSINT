"""Username enumeration across social platforms."""

from __future__ import annotations

import time
from typing import Any

import requests

PLATFORMS: list[dict[str, Any]] = [
    {
        "name": "GitHub",
        "url": "https://api.github.com/users/{}",
        "method": "api",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://github.com/{}",
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{}/about.json",
        "method": "api",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://reddit.com/u/{}",
    },
    {
        "name": "Twitter/X",
        "url": "https://twitter.com/{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://twitter.com/{}",
    },
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{}/",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.instagram.com/{}",
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.tiktok.com/@{}",
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.youtube.com/@{}",
    },
    {
        "name": "Twitch",
        "url": "https://www.twitch.tv/{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.twitch.tv/{}",
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{}/",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.pinterest.com/{}",
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/_/api/1.0/user/lookup.json?username={}",
        "method": "api",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://keybase.io/{}",
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://medium.com/@{}",
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://dev.to/{}",
    },
    {
        "name": "HackerNews",
        "url": "https://hacker-news.firebaseio.com/v0/user/{}.json",
        "method": "api_null",
        "profile_url": "https://news.ycombinator.com/user?id={}",
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://t.me/{}",
    },
    {
        "name": "Mastodon",
        "url": "https://mastodon.social/@{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://mastodon.social/@{}",
    },
    {
        "name": "Gitlab",
        "url": "https://gitlab.com/{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://gitlab.com/{}",
    },
    {
        "name": "npm",
        "url": "https://www.npmjs.com/~{}",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://www.npmjs.com/~{}",
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{}/",
        "method": "status",
        "found_status": 200,
        "not_found_status": 404,
        "profile_url": "https://pypi.org/user/{}",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def check_username(username: str) -> dict[str, Any]:
    """Search a username across social media platforms."""
    found: list[dict[str, str]] = []
    not_found: list[str] = []
    errors: list[str] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for platform in PLATFORMS:
        name = platform["name"]
        url = platform["url"].format(username)
        profile_url = platform["profile_url"].format(username)

        try:
            if platform.get("method") == "api_null":
                resp = session.get(url, timeout=6, allow_redirects=True)
                exists = resp.status_code == 200 and resp.text.strip() != "null"
            else:
                resp = session.get(url, timeout=6, allow_redirects=True)
                found_code = platform.get("found_status", 200)
                not_found_code = platform.get("not_found_status", 404)
                exists = resp.status_code == found_code and resp.status_code != not_found_code

            if exists:
                found.append({"platform": name, "url": profile_url})
            else:
                not_found.append(name)

        except requests.exceptions.Timeout:
            errors.append(f"{name} (timeout)")
        except requests.exceptions.RequestException:
            errors.append(f"{name} (error)")

        time.sleep(0.15)  # gentle rate limiting

    return {
        "status": "ok",
        "username": username,
        "found_count": len(found),
        "found": found,
        "not_found": not_found,
        "errors": errors,
        "total_checked": len(PLATFORMS),
    }
