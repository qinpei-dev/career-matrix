"""Lightweight, configuration-backed authentication for the local demo."""

from __future__ import annotations

from hmac import compare_digest


class DemoAuthenticationError(ValueError):
    """The request did not contain a valid configured demo credential."""


def authenticate_demo_token(
    authorization: str | None,
    token_to_email: dict[str, str],
) -> str:
    """Resolve a strict Bearer credential without disclosing the presented token."""
    if authorization is None:
        raise DemoAuthenticationError

    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not token
        or any(character.isspace() for character in token)
    ):
        raise DemoAuthenticationError

    presented = token.encode("utf-8")
    matched_email: str | None = None
    for configured_token, configured_email in token_to_email.items():
        candidate = configured_token.encode("utf-8")
        if compare_digest(presented, candidate):
            matched_email = configured_email.strip().lower()

    if not matched_email:
        raise DemoAuthenticationError
    return matched_email
