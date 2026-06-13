from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..deps import require_admin
from ..models.group import RecordingGroup
from ..models.user import User
from ..schemas.user import UserCreate, UserGroupAssignment, UserOut, UserUpdate
from ..security import get_password_hash

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await session.execute(
        select(User).order_by(User.username).options(selectinload(User.group_access))
    )
    return [UserOut.model_validate(u) for u in result.scalars()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(
        username=body.username,
        password_hash=get_password_hash(body.password),
        role=body.role,
    )
    session.add(user)
    await session.flush()
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.group_access))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.username is not None:
        user.username = body.username
    if body.password is not None:
        user.password_hash = get_password_hash(body.password)
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False


@router.put("/{user_id}/groups", response_model=UserOut)
async def assign_groups(
    user_id: int,
    body: UserGroupAssignment,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.group_access))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.group_ids:
        groups_result = await session.execute(
            select(RecordingGroup).where(RecordingGroup.id.in_(body.group_ids))
        )
        user.group_access = list(groups_result.scalars())
    else:
        user.group_access = []

    return UserOut.model_validate(user)
