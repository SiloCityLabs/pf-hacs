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
    API_USER_AGENT,
    APP_SCHEME,
    AUDIENCE,
    AUTH_BASE,
    AUTH_USER_AGENT,
    CLIENT_ID,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_UI_LOCALES,
    REDIRECT_URI,
    SCOPE,
)

_LOGGER = logging.getLogger(__name__)

_APP_CALLBACK_RE = re.compile(
    r"com\.planetfitness\.pfmobileauth://callback\?[^\s\"'<>\\]+",
    re.I,
)
_RESUME_RE = re.compile(
    r"https?://login\.planetfitness\.com/authorize/resume\?[^\s\"'<>\\]+",
    re.I,
)


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


def _extract_app_callback(text: str | None) -> str | None:
    if not text:
        return None
    match = _APP_CALLBACK_RE.search(text.replace("&amp;", "&"))
    return match.group(0) if match else None


def _extract_hidden_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", html, flags=re.I):
        if not re.search(r'type=["\']hidden["\']', tag, flags=re.I):
            # Still accept code/state inputs without type=hidden
            if not re.search(r'name=["\'](state|code)["\']', tag, flags=re.I):
                continue
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.I)
        val_m = re.search(r'value=["\']([^"\']*)["\']', tag, flags=re.I)
        if name_m:
            fields[name_m.group(1)] = val_m.group(1) if val_m else ""
    return fields


def _extract_form_action(html: str, current_url: str) -> str | None:
    match = re.search(
        r'<form[^>]*data-form-primary=["\']true["\'][^>]*action=["\']([^"\']*)["\']',
        html,
        flags=re.I,
    )
    if not match:
        match = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, flags=re.I)
    if not match:
        # Auth0 ULP often omits action (POST to current URL)
        if re.search(r'<form[^>]*method=["\']post["\']', html, flags=re.I):
            return current_url
        return None
    action = match.group(1).strip() or current_url
    return urljoin(current_url, action)


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
    """Begin Auth0 authorize (connection=email) and return the challenge session."""
    verifier, challenge = _pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()
    jar = aiohttp.CookieJar(unsafe=True)
    http = aiohttp.ClientSession(
        cookie_jar=jar,
        headers={
            "User-Agent": AUTH_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

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
            # Same extras the official app LoginUniversal() sends
            "ui_locales": DEFAULT_UI_LOCALES,
            "ext-countryCode": DEFAULT_COUNTRY_CODE,
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
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": AUTH_BASE,
            "Referer": auth.challenge_url,
        }
        form = {"state": auth.form_state, "code": code}

        redirect_url = await _post_and_follow_to_app_scheme(
            auth.http, auth.challenge_url, form, headers
        )
        auth_code = _parse_auth_code(redirect_url)
        _LOGGER.debug("Captured Auth0 authorization code")

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
        await close_auth_session(auth)


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
    """POST the OTP form and follow redirects/forms until the app callback URL."""
    status, current, body, loc = await _request(
        http, "POST", url, data=form, headers=headers
    )
    _LOGGER.debug(
        "OTP POST -> status=%s loc=%s url=%s body_len=%s",
        status,
        loc,
        current,
        len(body),
    )

    for hop in range(12):
        callback = _coerce_callback(loc, body, current)
        if callback:
            return callback

        if _looks_like_invalid_code(body):
            raise PlanetFitnessAuthError(
                "Auth0 rejected the code (invalid or expired)",
                code="invalid_code",
            )

        # Intermediate Auth0 resume / continue form (common on New Universal Login)
        resume = None
        if loc and "authorize/resume" in loc:
            resume = loc
        else:
            match = _RESUME_RE.search(body.replace("&amp;", "&"))
            if match:
                resume = match.group(0)

        next_action = _extract_form_action(body, current)
        next_fields = _extract_hidden_fields(body)

        if resume and not next_action:
            _LOGGER.debug("Following resume redirect hop=%s -> %s", hop, resume[:80])
            status, current, body, loc = await _request(http, "GET", resume)
            continue

        if next_action and (
            "resume" in next_action
            or "callback" in next_action
            or next_action.startswith(APP_SCHEME)
            or hop == 0
            or "authorize" in next_action
        ):
            # Avoid re-posting the OTP challenge form forever
            if 'name="code"' in body and hop > 0 and "resume" not in next_action:
                raise PlanetFitnessAuthError(
                    "Still on code challenge after submit — code may be wrong",
                    code="invalid_code",
                )
            post_headers = {
                **headers,
                "Referer": current,
                "Origin": AUTH_BASE,
            }
            # For resume continue forms, state hidden field is enough
            data = next_fields or form
            if next_action.startswith(APP_SCHEME):
                return next_action
            _LOGGER.debug(
                "Submitting continue form hop=%s action=%s fields=%s",
                hop,
                next_action[:100],
                list(data),
            )
            status, current, body, loc = await _request(
                http, "POST", next_action, data=data, headers=post_headers
            )
            continue

        if loc and loc.startswith("http"):
            _LOGGER.debug("Following http Location hop=%s -> %s", hop, loc[:100])
            status, current, body, loc = await _request(http, "GET", loc)
            continue

        _LOGGER.warning(
            "Auth redirect stuck hop=%s status=%s current=%s loc=%s snippet=%s",
            hop,
            status,
            current[:120],
            (loc or "")[:120],
            body[:240].replace("\n", " "),
        )
        break

    raise PlanetFitnessAuthError(
        "Could not capture app redirect after submitting code",
        code="redirect_failed",
    )


def _coerce_callback(loc: str | None, body: str, current: str) -> str | None:
    for candidate in (loc, current, body):
        if not candidate:
            continue
        if candidate.startswith(APP_SCHEME):
            return candidate
        found = _extract_app_callback(candidate)
        if found:
            return found
    return None


def _looks_like_invalid_code(body: str) -> bool:
    if not body:
        return False
    if 'name="code"' not in body:
        return False
    return bool(
        re.search(
            r"(invalid|incorrect|expired|wrong code|try again)",
            body,
            flags=re.I,
        )
    )


async def _request(
    http: aiohttp.ClientSession,
    method: str,
    url: str,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, str, str | None]:
    """Perform one request without following redirects; return status/url/body/Location."""
    if url.startswith(APP_SCHEME):
        return 302, url, "", url

    try:
        async with http.request(
            method,
            url,
            data=data,
            headers=headers,
            allow_redirects=False,
        ) as resp:
            # Raw Location first (custom schemes may break yarl URL helpers)
            loc = resp.headers.get("Location") or resp.headers.get("location")
            try:
                body = await resp.text(errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
            final = str(resp.url)
            return resp.status, final, body, loc
    except aiohttp.InvalidURL as err:
        # Some aiohttp/yarl paths raise when encountering the app scheme
        text = str(err)
        callback = _extract_app_callback(text) or (
            text if text.startswith(APP_SCHEME) else None
        )
        if callback:
            return 302, callback, "", callback
        raise PlanetFitnessAuthError(text, code="redirect_failed") from err
    except aiohttp.ClientError as err:
        text = str(err)
        callback = _extract_app_callback(text)
        if callback:
            return 302, callback, "", callback
        if APP_SCHEME in text:
            # e.g. "Cannot connect to host com.planetfitness..."
            m = re.search(r"(com\.planetfitness\.pfmobileauth://\S+)", text)
            if m:
                return 302, m.group(1).rstrip("',)"), "", m.group(1).rstrip("',)")
        raise


def _parse_auth_code(redirect_url: str) -> str:
    qs = parse_qs(urlparse(redirect_url).query)
    code = qs.get("code", [None])[0]
    if code:
        return code
    err = qs.get("error", [None])[0]
    if err:
        desc = qs.get("error_description", [""])[0]
        raise PlanetFitnessAuthError(
            f"Auth0 rejected login: {err}"
            + (f" ({desc})" if desc else ""),
            code="auth0_denied",
        )
    raise PlanetFitnessAuthError(
        f"No authorization code in redirect: {redirect_url}",
        code="redirect_failed",
    )


async def _fetch_account_device(
    http: aiohttp.ClientSession, access_token: str
) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": API_USER_AGENT,
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
