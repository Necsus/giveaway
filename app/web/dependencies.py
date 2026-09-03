from typing import cast

from fastapi import HTTPException, Request, status

from app.application.session import (
    SESSION_COOKIE_NAME,
    SessionIdentity,
    SessionSigner,
)


def require_session_identity(request: Request) -> SessionIdentity:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    session_signer = cast(
        SessionSigner,
        request.app.state.session_signer,
    )
    identity = session_signer.verify(cookie_value)

    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return identity
