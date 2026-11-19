"""Dependências compartilhadas dos endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import Resources


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources: Resources = request.app.state.resources
    async with resources.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
