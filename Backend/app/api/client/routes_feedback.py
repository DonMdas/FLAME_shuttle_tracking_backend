"""
Client Feedback Routes
Endpoints for users to submit and manage their feedback
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_authenticated_user
from app.api.client import controllers_feedback
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackDetail
from app.core.logger import logger, log_success, log_error


router = APIRouter(prefix="/client/feedback", tags=["Client Feedback"])


@router.post("/", response_model=FeedbackDetail)
async def submit_feedback(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Submit new feedback.
    
    Allows users to submit feedback about:
    - **Ride feedback**: Specific ride experience (requires vehicle_id)
    - **Route feedback**: Route or schedule issues (requires route_id)
    - **General feedback**: General suggestions or complaints
    - **Quick rating**: Simple rating without detailed feedback
    
    **Fields:**
    - `feedback_type`: ride, route, general, or quick_rating (required)
    - `category`: timing, cleanliness, driver, route, app, facility, other
    - `vehicle_id`: If feedback is about a specific vehicle
    - `route_id`: If feedback is about a specific route
    - `schedule_id`: If feedback is about a specific schedule
    - `rating`: 1-5 stars
    - `title`: Short summary
    - `description`: Detailed description
    - `issues`: Array of issues (delay, cleanliness, driver_behavior, etc.)
    - `is_anonymous`: Submit anonymously (email not visible to admin)
    
    Returns the created feedback with ID and status.
    
    Authentication: Required
    """
    try:
        user_id = current_user.get("user_id")
        feedback = await controllers_feedback.submit_feedback(db, user_id, feedback_data)
        log_success(
            "/client/feedback",
            f"Feedback submitted by user {user_id} - Type: {feedback_data.feedback_type}",
            current_user.get("email")
        )
        return feedback
    except Exception as e:
        log_error(
            "/client/feedback",
            e,
            current_user.get("email")
        )
        raise


@router.get("/my-history", response_model=List[FeedbackDetail])
async def get_my_feedback_history(
    status: Optional[str] = Query(None, description="Filter by status (pending, in_review, resolved, closed)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get all feedback submitted by the authenticated user.
    
    Returns user's feedback history with optional status filter.
    Shows admin responses if any.
    
    **Query Parameters:**
    - `status`: Filter by status (pending, in_review, resolved, closed, dismissed)
    - `skip`: Pagination offset
    - `limit`: Maximum items to return (default 100, max 100)
    
    Authentication: Required
    """
    try:
        user_id = current_user.get("user_id")
        feedbacks = await controllers_feedback.get_my_feedbacks(db, user_id, status, skip, limit)
        logger.info(f"/client/feedback/my-history - Retrieved {len(feedbacks)} feedbacks for user {user_id} - User: {current_user.get('email')}")
        return feedbacks
    except Exception as e:
        log_error(
            "/client/feedback/my-history",
            e,
            current_user.get("email")
        )
        raise


@router.get("/{feedback_id}", response_model=FeedbackDetail)
async def get_my_feedback_details(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get details of a specific feedback.
    
    Users can only view their own feedback.
    Shows admin response if any.
    
    Authentication: Required
    """
    try:
        user_id = current_user.get("user_id")
        feedback = await controllers_feedback.get_my_feedback_details(db, user_id, feedback_id)
        logger.info(f"/client/feedback/{{id}} - Retrieved feedback {feedback_id} for user {user_id} - User: {current_user.get('email')}")
        return feedback
    except Exception as e:
        log_error(
            "/client/feedback/{id}",
            e,
            current_user.get("email")
        )
        raise


@router.patch("/{feedback_id}", response_model=FeedbackDetail)
async def update_my_feedback(
    feedback_id: int,
    feedback_data: FeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Update own feedback.
    
    **Restrictions:**
    - Can only edit own feedback
    - Can only edit within 24 hours of submission
    - Cannot edit resolved or closed feedback
    
    **Editable fields:**
    - `title`: Feedback title
    - `description`: Detailed description
    - `rating`: Rating (1-5)
    - `issues`: List of issues
    
    Authentication: Required
    """
    try:
        user_id = current_user.get("user_id")
        feedback = await controllers_feedback.update_my_feedback(db, user_id, feedback_id, feedback_data)
        log_success(
            "/client/feedback/{id}",
            f"Updated feedback {feedback_id} by user {user_id}",
            current_user.get("email")
        )
        return feedback
    except Exception as e:
        log_error(
            "/client/feedback/{id}",
            e,
            current_user.get("email")
        )
        raise


@router.delete("/{feedback_id}")
async def delete_my_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Delete own feedback.
    
    **Restrictions:**
    - Can only delete own feedback
    - Can only delete within 24 hours of submission
    - Cannot delete resolved or closed feedback
    
    **Note:** Consider editing instead of deleting to preserve history.
    
    Authentication: Required
    """
    try:
        user_id = current_user.get("user_id")
        result = await controllers_feedback.delete_my_feedback(db, user_id, feedback_id)
        log_success(
            "/client/feedback/{id}",
            f"Deleted feedback {feedback_id} by user {user_id}",
            current_user.get("email")
        )
        return result
    except Exception as e:
        log_error(
            "/client/feedback/{id}",
            e,
            current_user.get("email")
        )
        raise
