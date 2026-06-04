from __future__ import annotations

import requests


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            )
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text
