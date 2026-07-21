"""Auth0 passwordless (email code) login for Planet Fitness."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp

from .const import (
    API_BASE,
    APP_SCHEME,
    AUDIENCE,
    AUTH_BASE,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        match = None
        for k, v in cur.items():
            if k.lower() == key.lower():
                match = v
                break
        if match is None:
            return None
        cur = match
    return cur


@dataclass
class AuthSession:
    """In-progress Auth0 email-code login (keeps cookies between steps)."""

    email: str
    verifier: str
    challenge_url: str
    form_state: str
    http: aiohttp.ClientSession


@dataclass
class LoginResult:
    """Successful login outcome stored on the config entry."""

    email: str
    account_id: str
    device_id: str
    access_token: str | None = None
    refresh_token: str | None = None


class PlanetFitnessAuthError(Exception):
    """Raised when Auth0 / mobile API login fails."""

    def __init__(self, message: str, *, code: str = "auth_failed") -> None:
        super().__init__(message)
        self.code = code


async def start_email_login(email: str) -> AuthSession:
    """Begin Auth0 authorize (connection=email) and return the challenge session.

    Auth0 emails a 6-digit code to ``email``. Caller must eventually close
    ``AuthSession.http`` (see ``complete_email_login`` / config flow).
    """
    verifier, challenge = _pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()
    jar = aiohttp.CookieJar(unsafe=True)
    http = aiohttp.ClientSession(cookie_jar=jar, headers={"User-Agent": USER_AGENT})

    authorize = f"{AUTH_BASE}/authorize?" + urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "audience": AUDIENCE,
            "connection": "email",
            "login_hint": email,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "prompt": "login",
        }
    )

    try:
        async with http.get(authorize, allow_redirects=True) as resp:
            html = await resp.text()
            challenge_url = str(resp.url)
            status = resp.status
    except Exception:
        await http.close()
        raise

    if status >= 400 or 'name="code"' not in html:
        await http.close()
        raise PlanetFitnessAuthError(
            f"Did not reach code challenge page ({status})",
            code="cannot_connect",
        )

    match = re.search(r'name="state"\s+value="([^"]+)"', html)
    if not match:
        await http.close()
        raise PlanetFitnessAuthError(
            "Missing state on challenge page", code="cannot_connect"
        )

    return AuthSession(
        email=email,
        verifier=verifier,
        challenge_url=challenge_url,
        form_state=match.group(1),
        http=http,
    )


async def complete_email_login(auth: AuthSession, code: str) -> LoginResult:
    """Submit the email OTP, exchange the auth code, and load account/device ids."""
    try:
        code = re.sub(r"\s+", "", code)
        if not re.fullmatch(r"\d{6}", code):
            raise PlanetFitnessAuthError("Code must be 6 digits", code="invalid_code")

        headers = {
            "Accept": "text/html,application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": auth.challenge_url,
        }
        form = {"state": auth.form_state, "code": code}

        redirect_url = await _post_and_follow_to_app_scheme(
            auth.http, auth.challenge_url, form, headers
        )
        auth_code = _parse_auth_code(redirect_url)

        token_body = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code_verifier": auth.verifier,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        }
        async with auth.http.post(
            f"{AUTH_BASE}/oauth/token",
            data=token_body,
            headers={"Accept": "application/json"},
        ) as resp:
            tokens = await resp.json(content_type=None)
            if resp.status >= 400 or "access_token" not in tokens:
                raise PlanetFitnessAuthError(
                    f"Token exchange failed: {tokens}",
                    code="invalid_auth",
                )

        access = tokens["access_token"]
        refresh = tokens.get("refresh_token")
        account_id, device_id = await _fetch_account_device(auth.http, access)

        return LoginResult(
            email=auth.email,
            account_id=account_id,
            device_id=device_id,
            access_token=access,
            refresh_token=refresh,
        )
    finally:
        if not auth.http.closed:
            await auth.http.close()


async def close_auth_session(auth: AuthSession | None) -> None:
    """Close the temporary HTTP session if still open."""
    if auth is not None and not auth.http.closed:
        await auth.http.close()


async def _post_and_follow_to_app_scheme(
    http: aiohttp.ClientSession,
    url: str,
    form: dict[str, str],
    headers: dict[str, str],
) -> str:
    """POST the OTP form and follow redirects until the app callback URL."""
    async with http.post(url, data=form, headers=headers, allow_redirects=False) as resp:
        loc = resp.headers.get("Location")
        body = await resp.text()
        current = loc or str(resp.url)

    if current.startswith(APP_SCHEME):
        return current

    found = re.search(r"com\.planetfitness\.pfmobileauth://callback\?[^\s\"'<>]+", body)
    if found:
        return found.group(0).replace("&amp;", "&")

    for _ in range(10):
        if current.startswith(APP_SCHEME):
            return current
        if not current.startswith("http"):
            break
        try:
            async with http.get(current, allow_redirects=False) as resp:
                loc = resp.headers.get("Location")
                body = await resp.text()
                if loc and loc.startswith(APP_SCHEME):
                    return loc
                if loc:
                    current = urljoin(current, loc)
                    continue
                found = re.search(
                    r"com\.planetfitness\.pfmobileauth://callback\?[^\s\"'<>]+", body
                )
                if found:
                    return found.group(0).replace("&amp;", "&")
                if "Enter Code" in body or re.search(
                    r"invalid|incorrect|expired", body, re.I
                ):
                    raise PlanetFitnessAuthError(
                        "Auth0 rejected the code (invalid or expired)",
                        code="invalid_code",
                    )
                break
        except aiohttp.InvalidURL as err:
            m = re.search(r"(com\.planetfitness\.pfmobileauth://[^\s]+)", str(err))
            if m:
                return m.group(1)
            raise PlanetFitnessAuthError(str(err), code="cannot_connect") from err

    raise PlanetFitnessAuthError(
        "Could not capture app redirect after submitting code",
        code="cannot_connect",
    )


def _parse_auth_code(redirect_url: str) -> str:
    qs = urlparse(redirect_url).query
    code = parse_qs(qs).get("code", [None])[0]
    if not code:
        raise PlanetFitnessAuthError(
            f"No authorization code in redirect: {redirect_url}",
            code="cannot_connect",
        )
    return code


async def _fetch_account_device(
    http: aiohttp.ClientSession, access_token: str
) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    details: dict[str, Any] = {}
    async with http.get(f"{API_BASE}/user-details?", headers=headers) as resp:
        if resp.status == 200:
            details = await resp.json(content_type=None)
        else:
            async with http.get(f"{API_BASE}/profile", headers=headers) as resp2:
                if resp2.status != 200:
                    text = await resp2.text()
                    raise PlanetFitnessAuthError(
                        f"Failed to load profile ({resp2.status}): {text[:200]}",
                        code="cannot_connect",
                    )
                details = await resp2.json(content_type=None)

    root = details.get("result", details)
    account_id = _dig(root, "user", "accountId") or _dig(root, "accountId")
    device_id = _dig(root, "user", "personalization", "deviceId") or _dig(
        root, "personalization", "deviceId"
    )
    if not account_id or not device_id:
        raise PlanetFitnessAuthError(
            "Profile missing accountId or personalization.deviceId "
            "(open the official app once to register a device id, then retry)",
            code="missing_device",
        )
    return str(account_id), str(device_id)
