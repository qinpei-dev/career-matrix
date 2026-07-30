"""Workspace dashboard, search, notification, and settings endpoints."""

from fastapi import APIRouter, Depends, Query

from ...application.workspace_service import WorkspaceService
from ...schemas.workspace import (
    DashboardRead,
    NotificationRead,
    ProviderStatuses,
    SearchResponse,
    UserSettingsRead,
    UserSettingsUpdate,
)
from ..dependencies import get_workspace_service

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(
    service: WorkspaceService = Depends(get_workspace_service),
) -> DashboardRead:
    return service.dashboard()


@router.get("/search", response_model=SearchResponse)
def search_workspace(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=30, ge=1, le=100),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SearchResponse:
    return service.search(q, limit)


@router.get("/notifications", response_model=list[NotificationRead])
def get_notifications(
    limit: int = Query(default=10, ge=1, le=50),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[NotificationRead]:
    return service.notifications(limit)


@router.get("/settings", response_model=UserSettingsRead)
def get_user_settings(
    service: WorkspaceService = Depends(get_workspace_service),
) -> UserSettingsRead:
    return service.get_settings()


@router.patch("/settings", response_model=UserSettingsRead)
def update_user_settings(
    payload: UserSettingsUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
) -> UserSettingsRead:
    return service.update_settings(payload)


@router.get("/providers", response_model=ProviderStatuses)
def get_provider_statuses(
    service: WorkspaceService = Depends(get_workspace_service),
) -> ProviderStatuses:
    return service.provider_statuses()
