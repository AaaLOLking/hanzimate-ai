from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.auth import CurrentUser, SessionDependency
from app.models import Workspace, utc_now
from app.schemas import WorkspaceCreate, WorkspaceOutput, WorkspaceUpdate

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


def get_owned_workspace(
    session: SessionDependency, user: CurrentUser, workspace_id: str
) -> Workspace:
    workspace = session.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user.id)
    )
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("", response_model=list[WorkspaceOutput])
def list_workspaces(session: SessionDependency, user: CurrentUser) -> list[Workspace]:
    return list(
        session.scalars(
            select(Workspace)
            .where(Workspace.user_id == user.id, Workspace.status != "archived")
            .order_by(Workspace.last_opened_at.desc())
        )
    )


@router.post("", response_model=WorkspaceOutput, status_code=201)
def create_workspace(
    payload: WorkspaceCreate, session: SessionDependency, user: CurrentUser
) -> Workspace:
    workspace = Workspace(user_id=user.id, **payload.model_dump())
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceOutput)
def restore_workspace(
    workspace_id: str, session: SessionDependency, user: CurrentUser
) -> Workspace:
    workspace = get_owned_workspace(session, user, workspace_id)
    workspace.last_opened_at = utc_now()
    session.commit()
    session.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOutput)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    session: SessionDependency,
    user: CurrentUser,
) -> Workspace:
    workspace = get_owned_workspace(session, user, workspace_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    workspace.last_opened_at = utc_now()
    session.commit()
    session.refresh(workspace)
    return workspace
