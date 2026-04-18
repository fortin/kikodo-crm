"""
Client for the www.kikodo.app Blog Posts API.
Used when publishing a newsletter issue: create/update the corresponding blog post.
"""

import logging
from typing import Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def publish_blog_post(
    *,
    title: str,
    slug: str,
    body: str,
    body_format: str = "html",
    meta_title: str = "",
    meta_description: str = "",
    published: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Create or update a blog post on www.kikodo.app.

    Uses POST to create; if slug exists the API returns 400 (caller may then PATCH by slug).
    Returns (success, error_message). error_message is None on success.
    """
    base_url = (getattr(settings, "KIKODO_BLOG_API_URL", "") or "").rstrip("/")
    token = getattr(settings, "KIKODO_BLOG_API_TOKEN", "") or ""
    if not base_url or not token:
        return False, "KIKODO_BLOG_API_URL and KIKODO_BLOG_API_TOKEN must be set"

    url = f"https://www.kikodo.app/api/blog/posts/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title[:500],
        "slug": slug[:500],
        "body": body,
        "body_format": body_format,
        "published": published,
    }
    if meta_title:
        payload["meta_title"] = meta_title[:60]
    if meta_description:
        payload["meta_description"] = meta_description[:320]

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        logger.exception("Blog API request failed: %s", e)
        return False, str(e)

    if resp.status_code in (200, 201):
        return True, None

    # If slug already exists, try PATCH to update
    if resp.status_code == 400:
        try:
            err_data = resp.json()
            if isinstance(err_data.get("slug"), list) and any(
                "already exists" in str(s) for s in err_data["slug"]
            ):
                patch_url = f"https://www.kikodo.app/api/blog/posts/{slug.rstrip('/')}/"
                patch_resp = requests.patch(
                    patch_url, json=payload, headers=headers, timeout=30
                )
                if patch_resp.status_code == 200:
                    return True, None
                try:
                    msg = patch_resp.json().get("detail", patch_resp.text)[:500]
                except Exception:
                    msg = patch_resp.text[:500] or f"HTTP {patch_resp.status_code}"
                return False, msg
        except Exception as e:
            logger.exception("Blog API PATCH after 400 failed: %s", e)

    try:
        err = resp.json()
        msg = err.get("slug", err.get("detail", resp.text))
        if isinstance(msg, list):
            msg = msg[0] if msg else resp.text
        msg = str(msg)[:500]
    except Exception:
        msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
    return False, msg
