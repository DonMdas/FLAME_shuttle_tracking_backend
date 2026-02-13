"""
Admin Feedback Routes
Endpoints for admin to manage all feedback
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user
from app.api.admin import controllers_feedback
from app.schemas.feedback import (
    FeedbackAdmin, FeedbackStats, FeedbackAnalytics,
    FeedbackStatusUpdate, FeedbackResponse, BulkStatusUpdate,
    BulkUpdateResult, FeedbackListResponse
)
from app.core.logger import logger, log_success, log_error


router = APIRouter(prefix="/admin/feedback", tags=["Admin Feedback"])


@router.get("/", response_model=FeedbackListResponse)
async def list_all_feedbacks(
    status: Optional[str] = Query(None, description="Filter by status"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    route_id: Optional[str] = Query(None, description="Filter by route"),
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle"),
    rating: Optional[int] = Query(None, description="Filter by rating", ge=1, le=5),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all feedbacks with filters and pagination.
    
    **Admin only endpoint**
    
    Supports filtering by:
    - Status (pending, in_review, resolved, closed, dismissed)
    - Feedback type (ride, route, general, quick_rating)
    - Category (timing, cleanliness, driver, etc.)
    - Priority (low, medium, high, critical)
    - Route, Vehicle, Rating
    - Date range
    
    Returns paginated results with total count.
    
    Authentication: Admin required
    """
    try:
        result = await controllers_feedback.list_all_feedbacks(
            db, status, feedback_type, category, priority,
            route_id, vehicle_id, rating, date_from, date_to,
            page, page_size
        )
        log_success("/admin/feedback", f"Listed feedbacks, page {page}", current_user.get("username"))
        return result
    except Exception as e:
        log_error("/admin/feedback", e, current_user.get("username"))
        raise


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get overall feedback statistics.
    
    **Admin only endpoint**
    
    Returns:
    - Total feedback count
    - Breakdown by status, type, category, priority
    - Average rating
    
    Useful for admin dashboard.
    
    Authentication: Admin required
    """
    try:
        stats = await controllers_feedback.get_feedback_statistics(db)
        log_success("/admin/feedback/stats", "Retrieved feedback statistics", current_user.get("username"))
        return stats
    except Exception as e:
        log_error("/admin/feedback/stats", e, current_user.get("username"))
        raise


@router.get("/analytics", response_model=FeedbackAnalytics)
async def get_feedback_analytics(
    date_from: Optional[datetime] = Query(None, description="Analytics from date"),
    date_to: Optional[datetime] = Query(None, description="Analytics to date"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed feedback analytics.
    
    **Admin only endpoint**
    
    Returns:
    - Total feedback and average rating in date range
    - Breakdown by route (with ratings)
    - Breakdown by vehicle (with ratings)
    - Breakdown by category
    - Common issues
    - Rating distribution
    
    Useful for identifying problem areas and trends.
    
    Authentication: Admin required
    """
    try:
        analytics = await controllers_feedback.get_feedback_analytics_admin(db, date_from, date_to)
        log_success("/admin/feedback/analytics", "Retrieved feedback analytics", current_user.get("username"))
        return analytics
    except Exception as e:
        log_error("/admin/feedback/analytics", e, current_user.get("username"))
        raise


@router.get("/{feedback_id}", response_model=FeedbackAdmin)
async def get_feedback_details(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed feedback information including user details.
    
    **Admin only endpoint**
    
    Returns complete feedback information including:
    - User email (unless anonymous)
    - All feedback details
    - Admin notes (internal)
    - Related entity information
    
    Authentication: Admin required
    """
    try:
        feedback = await controllers_feedback.get_feedback_details_admin(db, feedback_id)
        logger.info(f"/admin/feedback/{{id}} - Retrieved feedback {feedback_id} - User: {current_user.get('username')}")
        return feedback
    except Exception as e:
        log_error("/admin/feedback/{id}", e, current_user.get("username"))
        raise


@router.patch("/{feedback_id}/status", response_model=FeedbackAdmin)
async def update_feedback_status(
    feedback_id: int,
    status_data: FeedbackStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update feedback status and priority.
    
    **Admin only endpoint**
    
    Allows admin to:
    - Change status (pending, in_review, resolved, closed, dismissed)
    - Update priority (low, medium, high, critical)
    - Add internal admin notes
    
    When marking as resolved/closed, automatically records admin ID and timestamp.
    
    Authentication: Admin required
    """
    try:
        admin_id = current_user.get("admin_id")
        feedback = await controllers_feedback.update_feedback_status_admin(
            db, feedback_id, status_data, admin_id
        )
        log_success(
            "/admin/feedback/{id}/status",
            f"Updated feedback {feedback_id} status to {status_data.status}",
            current_user.get("username")
        )
        return feedback
    except Exception as e:
        log_error(
            "/admin/feedback/{id}/status",
            e,
            current_user.get("username")
        )
        raise


@router.post("/{feedback_id}/response", response_model=FeedbackAdmin)
async def respond_to_feedback(
    feedback_id: int,
    response_data: FeedbackResponse,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Add admin response to feedback.
    
    **Admin only endpoint**
    
    Allows admin to respond to user feedback.
    The response is visible to the user.
    Automatically moves feedback to "in_review" status.
    
    Authentication: Admin required
    """
    try:
        admin_id = current_user.get("admin_id")
        feedback = await controllers_feedback.respond_to_feedback_admin(
            db, feedback_id, response_data, admin_id
        )
        log_success(
            "/admin/feedback/{id}/response",
            f"Added response to feedback {feedback_id}",
            current_user.get("username")
        )
        return feedback
    except Exception as e:
        log_error(
            "/admin/feedback/{id}/response",
            e,
            current_user.get("username")
        )
        raise


@router.post("/bulk-update", response_model=BulkUpdateResult)
async def bulk_update_status(
    bulk_data: BulkStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk update feedback status.
    
    **Admin only endpoint**
    
    Update status for multiple feedbacks at once.
    Useful for batch operations like:
    - Closing all resolved feedbacks
    - Dismissing spam feedbacks
    - Marking multiple as in-review
    
    Returns count of successful and failed updates.
    
    Authentication: Admin required
    """
    try:
        admin_id = current_user.get("admin_id")
        result = await controllers_feedback.bulk_update_status_admin(db, bulk_data, admin_id)
        log_success(
            "/admin/feedback/bulk-update",
            f"Bulk updated {result.success_count} feedbacks to {bulk_data.status}",
            current_user.get("username")
        )
        return result
    except Exception as e:
        log_error(
            "/admin/feedback/bulk-update",
            e,
            current_user.get("username")
        )
        raise


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete feedback.
    
    **Admin only endpoint**
    
    Permanently delete feedback. Use with caution.
    Consider marking as "dismissed" instead for record keeping.
    
    Authentication: Admin required
    """
    try:
        result = await controllers_feedback.delete_feedback_admin(db, feedback_id)
        log_success(
            "/admin/feedback/{id}",
            f"Deleted feedback {feedback_id}",
            current_user.get("username")
        )
        return result
    except Exception as e:
        log_error(
            "/admin/feedback/{id}",
            e,
            current_user.get("username")
        )
        raise
