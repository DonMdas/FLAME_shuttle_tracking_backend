from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from datetime import datetime
from db import crud
from schemas.feedback import (
    FeedbackCreate, FeedbackUpdate, FeedbackStatusUpdate, FeedbackResponse,
    FeedbackBasic, FeedbackDetail, FeedbackAdmin, FeedbackStats, 
    FeedbackAnalytics, BulkStatusUpdate, BulkUpdateResult, FeedbackListResponse
)
import json


async def list_all_feedbacks(
    db: Session,
    status: Optional[str] = None,
    feedback_type: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    route_id: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    rating: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50
) -> FeedbackListResponse:
    """Get all feedbacks with filters and pagination (admin view)"""
    
    filters = {}
    if status:
        filters["status"] = status
    if feedback_type:
        filters["feedback_type"] = feedback_type
    if category:
        filters["category"] = category
    if priority:
        filters["priority"] = priority
    if route_id:
        filters["route_id"] = route_id
    if vehicle_id:
        filters["vehicle_id"] = vehicle_id
    if rating:
        filters["rating"] = rating
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    
    skip = (page - 1) * page_size
    feedbacks, total = crud.get_all_feedbacks(db, filters=filters, skip=skip, limit=page_size)
    
    # Convert to response models
    items = []
    for feedback in feedbacks:
        # Parse issues from JSON if present
        issues = None
        if feedback.issues:
            try:
                issues = json.loads(feedback.issues)
            except:
                issues = []
        
        items.append(FeedbackBasic(
            id=feedback.id,
            user_id=feedback.user_id,
            is_anonymous=feedback.is_anonymous,
            feedback_type=feedback.feedback_type,
            category=feedback.category,
            vehicle_id=feedback.vehicle_id,
            route_id=feedback.route_id,
            schedule_id=feedback.schedule_id,
            rating=feedback.rating,
            title=feedback.title,
            status=feedback.status,
            priority=feedback.priority,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at
        ))
    
    total_pages = (total + page_size - 1) // page_size
    
    return FeedbackListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


async def get_feedback_details_admin(db: Session, feedback_id: int) -> FeedbackAdmin:
    """Get detailed feedback information (admin view)"""
    feedback_data = crud.get_feedback_with_details(db, feedback_id)
    
    if not feedback_data:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    return FeedbackAdmin(**feedback_data)


async def update_feedback_status_admin(
    db: Session, 
    feedback_id: int, 
    status_data: FeedbackStatusUpdate,
    admin_id: int
) -> FeedbackAdmin:
    """Update feedback status (admin action)"""
    feedback = crud.update_feedback_status(
        db,
        feedback_id=feedback_id,
        status=status_data.status,
        priority=status_data.priority,
        admin_notes=status_data.admin_notes,
        admin_id=admin_id
    )
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Get full details for response
    feedback_data = crud.get_feedback_with_details(db, feedback_id)
    return FeedbackAdmin(**feedback_data)


async def respond_to_feedback_admin(
    db: Session,
    feedback_id: int,
    response_data: FeedbackResponse,
    admin_id: int
) -> FeedbackAdmin:
    """Add admin response to feedback"""
    feedback = crud.add_admin_response(
        db,
        feedback_id=feedback_id,
        admin_response=response_data.admin_response,
        admin_id=admin_id
    )
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Get full details for response
    feedback_data = crud.get_feedback_with_details(db, feedback_id)
    return FeedbackAdmin(**feedback_data)


async def bulk_update_status_admin(
    db: Session,
    bulk_data: BulkStatusUpdate,
    admin_id: int
) -> BulkUpdateResult:
    """Bulk update feedback status"""
    result = crud.bulk_update_feedback_status(
        db,
        feedback_ids=bulk_data.feedback_ids,
        status=bulk_data.status,
        admin_notes=bulk_data.admin_notes,
        admin_id=admin_id
    )
    
    return BulkUpdateResult(
        success_count=result["success_count"],
        failed_count=result["failed_count"],
        updated_ids=result["updated_ids"],
        failed_ids=result["failed_ids"],
        message=f"Successfully updated {result['success_count']} feedbacks, {result['failed_count']} failed"
    )


async def get_feedback_statistics(db: Session) -> FeedbackStats:
    """Get feedback statistics"""
    stats = crud.get_feedback_stats(db)
    return FeedbackStats(**stats)


async def get_feedback_analytics_admin(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> FeedbackAnalytics:
    """Get detailed feedback analytics"""
    analytics = crud.get_feedback_analytics(db, date_from=date_from, date_to=date_to)
    return FeedbackAnalytics(**analytics, trend_data=None)  # trend_data can be added later


async def delete_feedback_admin(db: Session, feedback_id: int) -> dict:
    """Delete feedback (admin only)"""
    success = crud.delete_feedback(db, feedback_id)
    if not success:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    return {"message": f"Feedback {feedback_id} deleted successfully"}
