from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User

SessionDependency = Annotated[Session, Depends(get_session)]


def get_current_user(
    request: Request,
    session: SessionDependency,
    learner_id: Annotated[str | None, Header(alias="X-Learner-ID")] = None,
) -> User:
    settings = request.app.state.settings
    resolved_id = learner_id
    if not resolved_id and settings.app_env != "production":
        resolved_id = settings.demo_user_id
    if not resolved_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        resolved_id = str(UUID(resolved_id))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Learner-ID must be a valid UUID",
        ) from error

    user = session.scalar(select(User).where(User.id == resolved_id, User.deleted_at.is_(None)))
    if user:
        return user
    if settings.app_env == "production":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown account")

    email = (
        settings.demo_user_email
        if resolved_id == settings.demo_user_id
        else f"learner-{resolved_id}@local.hanzimate"
    )
    user = User(id=resolved_id, email=email, display_name="Alex Morgan")
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
        return user
    except IntegrityError:
        # Several dashboard requests can bootstrap the same development user in parallel.
        # The unique identity wins; all other requests reuse it after rolling back.
        session.rollback()
        user = session.scalar(select(User).where(User.id == resolved_id, User.deleted_at.is_(None)))
        if user is None:
            raise
        return user


CurrentUser = Annotated[User, Depends(get_current_user)]
