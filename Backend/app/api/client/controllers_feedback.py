from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException
from db import crud
from schemas.feedback import (
    FeedbackCreate, FeedbackUpdate, FeedbackDetail
)
import json


async def submit_feedback(db: Session, user_id: int, feedback_data: FeedbackCreate) -> FeedbackDetail:
    """Submit new feedback"""
    # Validate that referenced entities exist if provided
    if feedback_data.vehicle_id:
        vehicle = crud.get_vehicle(db, feedback_data.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail=f"Vehicle {feedback_data.vehicle_id} not found")
    
    if feedback_data.route_id:
        route = crud.get_route(db, feedback_data.route_id)
        if not route:
            raise HTTPException(status_code=404, detail=f"Route {feedback_data.route_id} not found")
    
    if feedback_data.schedule_id:
        schedule = crud.get_schedule(db, feedback_data.schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail=f"Schedule {feedback_data.schedule_id} not found")
    
    # Create feedback
    feedback_dict = feedback_data.dict()
    feedback = crud.create_feedback(db, user_id=user_id, feedback_data=feedback_dict)
    
    # Parse issues from JSON for response
    issues = None
    if feedback.issues:
        try:
            issues = json.loads(feedback.issues)
        except:
            issues = []
    
    return FeedbackDetail(
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
        description=feedback.description,
        issues=issues,
        status=feedback.status,
        priority=feedback.priority,
        admin_response=feedback.admin_response,
        resolved_at=feedback.resolved_at,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at
    )


async def get_my_feedbacks(
    db: Session, 
    user_id: int,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[FeedbackDetail]:
    """Get all feedbacks submitted by the authenticated user"""
    feedbacks = crud.get_user_feedbacks(db, user_id=user_id, status=status, skip=skip, limit=limit)
    
    result = []
    for feedback in feedbacks:
        # Parse issues from JSON
        issues = None
        if feedback.issues:
            try:
                issues = json.loads(feedback.issues)
            except:
                issues = []
        
        result.append(FeedbackDetail(
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
            description=feedback.description,
            issues=issues,
            status=feedback.status,
            priority=feedback.priority,
            admin_response=feedback.admin_response,
            resolved_at=feedback.resolved_at,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at
        ))
    
    return result


async def get_my_feedback_details(db: Session, user_id: int, feedback_id: int) -> FeedbackDetail:
    """Get specific feedback details (only if owned by user)"""
    feedback = crud.get_feedback(db, feedback_id)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    if feedback.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this feedback")
    
    # Parse issues from JSON
    issues = None
    if feedback.issues:
        try:
            issues = json.loads(feedback.issues)
        except:
            issues = []
    
    return FeedbackDetail(
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
        description=feedback.description,
        issues=issues,
        status=feedback.status,
        priority=feedback.priority,
        admin_response=feedback.admin_response,
        resolved_at=feedback.resolved_at,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at
    )


async def update_my_feedback(
    db: Session, 
    user_id: int, 
    feedback_id: int, 
    feedback_data: FeedbackUpdate
) -> FeedbackDetail:
    """Update user's own feedback (only within 24 hours and if not resolved)"""
    from datetime import timedelta
    
    feedback = crud.get_feedback(db, feedback_id)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    if feedback.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this feedback")
    
    # Check if feedback is still editable (within 24 hours)
    time_since_creation = crud.get_ist_now() - feedback.created_at
    if time_since_creation > timedelta(hours=24):
        raise HTTPException(status_code=400, detail="Feedback can only be edited within 24 hours of submission")
    
    # Check if feedback is not already resolved/closed
    if feedback.status in ["resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Cannot edit resolved or closed feedback")
    
    # Update feedback
    update_dict = feedback_data.dict(exclude_unset=True)
    updated_feedback = crud.update_feedback(db, feedback_id, update_dict)
    
    if not updated_feedback:
        raise HTTPException(status_code=500, detail="Failed to update feedback")
    
    # Parse issues from JSON
    issues = None
    if updated_feedback.issues:
        try:
            issues = json.loads(updated_feedback.issues)
        except:
            issues = []
    
    return FeedbackDetail(
        id=updated_feedback.id,
        user_id=updated_feedback.user_id,
        is_anonymous=updated_feedback.is_anonymous,
        feedback_type=updated_feedback.feedback_type,
        category=updated_feedback.category,
        vehicle_id=updated_feedback.vehicle_id,
        route_id=updated_feedback.route_id,
        schedule_id=updated_feedback.schedule_id,
        rating=updated_feedback.rating,
        title=updated_feedback.title,
        description=updated_feedback.description,
        issues=issues,
        status=updated_feedback.status,
        priority=updated_feedback.priority,
        admin_response=updated_feedback.admin_response,
        resolved_at=updated_feedback.resolved_at,
        created_at=updated_feedback.created_at,
        updated_at=updated_feedback.updated_at
    )


async def delete_my_feedback(db: Session, user_id: int, feedback_id: int) -> dict:
    """Delete user's own feedback (only within 24 hours and if not resolved)"""
    from datetime import timedelta
    
    feedback = crud.get_feedback(db, feedback_id)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    if feedback.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this feedback")
    
    # Check if feedback is still deletable (within 24 hours)
    time_since_creation = crud.get_ist_now() - feedback.created_at
    if time_since_creation > timedelta(hours=24):
        raise HTTPException(status_code=400, detail="Feedback can only be deleted within 24 hours of submission")
    
    # Check if feedback is not already resolved/closed
    if feedback.status in ["resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Cannot delete resolved or closed feedback")
    
    success = crud.delete_feedback(db, feedback_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete feedback")
    
    return {"message": "Feedback deleted successfully"}
