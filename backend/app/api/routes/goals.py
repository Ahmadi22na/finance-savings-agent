import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalOut, GoalContribution, GoalReorderRequest
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.create_goal(db, current_user, data)


@router.get("", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return goal_service.list_goals_for_user(db, current_user)


@router.put("/reorder", response_model=list[GoalOut])
def reorder_goals(
    data: GoalReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.reorder_goals(db, current_user, data)


@router.post("/{goal_id}/contribute", response_model=GoalOut)
def contribute_to_goal(
    goal_id: uuid.UUID,
    data: GoalContribution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.contribute_to_goal(db, current_user, goal_id, data)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal_service.delete_goal(db, current_user, goal_id)
