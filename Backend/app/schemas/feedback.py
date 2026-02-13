from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============ Enums/Constants ============

FEEDBACK_TYPES = ["ride", "route", "general", "quick_rating"]
CATEGORIES = ["timing", "cleanliness", "driver", "route", "app", "facility", "overcrowding", "safety", "other"]
STATUSES = ["pending", "in_review", "resolved", "closed", "dismissed"]
PRIORITIES = ["low", "medium", "high", "critical"]
COMMON_ISSUES = ["delay", "cleanliness", "driver_behavior", "overcrowding", "route_deviation", 
                 "uncomfortable_ride", "ac_not_working", "unsafe_driving", "rude_staff", "other"]


# ============ Request Schemas ============

class FeedbackCreate(BaseModel):
    """Schema for creating feedback"""
    feedback_type: str = Field(..., description="Type of feedback: ride, route, general, quick_rating")
    category: Optional[str] = Field(None, description="Category: timing, cleanliness, driver, route, app, facility, other")
    vehicle_id: Optional[int] = Field(None, description="Vehicle ID if feedback is about a specific vehicle")
    route_id: Optional[int] = Field(None, description="Route ID if feedback is about a specific route")
    schedule_id: Optional[int] = Field(None, description="Schedule ID if feedback is about a specific schedule")
    rating: Optional[int] = Field(None, description="Rating from 1 to 5", ge=1, le=5)
    title: Optional[str] = Field(None, description="Feedback title", max_length=255)
    description: Optional[str] = Field(None, description="Detailed description", max_length=2000)
    issues: Optional[List[str]] = Field(None, description="List of issues")
    is_anonymous: bool = Field(False, description="Submit feedback anonymously")
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        if v not in FEEDBACK_TYPES:
            raise ValueError(f"feedback_type must be one of {FEEDBACK_TYPES}")
        return v
    
    @validator('category')
    def validate_category(cls, v):
        if v and v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v


class FeedbackUpdate(BaseModel):
    """Schema for updating feedback (user can edit their own feedback)"""
    title: Optional[str] = Field(None, description="Feedback title", max_length=255)
    description: Optional[str] = Field(None, description="Detailed description", max_length=2000)
    rating: Optional[int] = Field(None, description="Rating from 1 to 5", ge=1, le=5)
    issues: Optional[List[str]] = Field(None, description="List of issues")


class FeedbackStatusUpdate(BaseModel):
    """Schema for admin to update feedback status"""
    status: str = Field(..., description="Status: pending, in_review, resolved, closed, dismissed")
    priority: Optional[str] = Field(None, description="Priority: low, medium, high, critical")
    admin_notes: Optional[str] = Field(None, description="Internal admin notes", max_length=2000)
    
    @validator('status')
    def validate_status(cls, v):
        if v not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        return v


class FeedbackResponse(BaseModel):
    """Schema for admin to respond to feedback"""
    admin_response: str = Field(..., description="Response message to user", max_length=2000)


class BulkStatusUpdate(BaseModel):
    """Schema for bulk status updates"""
    feedback_ids: List[int] = Field(..., description="List of feedback IDs to update")
    status: str = Field(..., description="New status for all feedbacks")
    admin_notes: Optional[str] = Field(None, description="Admin notes for all feedbacks")
    
    @validator('status')
    def validate_status(cls, v):
        if v not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        return v


# ============ Response Schemas ============

class FeedbackBasic(BaseModel):
    """Basic feedback information"""
    id: int
    user_id: int
    is_anonymous: bool
    feedback_type: str
    category: Optional[str]
    vehicle_id: Optional[int]
    route_id: Optional[int]
    schedule_id: Optional[int]
    rating: Optional[int]
    title: Optional[str]
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackDetail(BaseModel):
    """Detailed feedback information"""
    id: int
    user_id: int
    is_anonymous: bool
    feedback_type: str
    category: Optional[str]
    vehicle_id: Optional[int]
    route_id: Optional[int]
    schedule_id: Optional[int]
    rating: Optional[int]
    title: Optional[str]
    description: Optional[str]
    issues: Optional[List[str]]
    status: str
    priority: str
    admin_response: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackAdmin(BaseModel):
    """Admin view of feedback with all details"""
    id: int
    user_id: int
    user_email: Optional[str]  # Include user email for admin
    is_anonymous: bool
    feedback_type: str
    category: Optional[str]
    vehicle_id: Optional[int]
    vehicle_name: Optional[str]
    route_id: Optional[int]
    route_name: Optional[str]
    schedule_id: Optional[int]
    rating: Optional[int]
    title: Optional[str]
    description: Optional[str]
    issues: Optional[List[str]]
    status: str
    priority: str
    admin_response: Optional[str]
    admin_notes: Optional[str]
    resolved_by: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackStats(BaseModel):
    """Feedback statistics"""
    total_feedback: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_category: Dict[str, int]
    by_priority: Dict[str, int]
    average_rating: Optional[float]
    total_with_rating: int


class FeedbackAnalytics(BaseModel):
    """Detailed analytics data"""
    date_range: Dict[str, Any]
    total_feedback: int
    average_rating: Optional[float]
    by_route: List[Dict[str, Any]]
    by_vehicle: List[Dict[str, Any]]
    by_category: Dict[str, int]
    common_issues: List[Dict[str, Any]]
    rating_distribution: Dict[str, int]
    trend_data: Optional[List[Dict[str, Any]]]


class BulkUpdateResult(BaseModel):
    """Result of bulk update operation"""
    success_count: int
    failed_count: int
    updated_ids: List[int]
    failed_ids: List[int]
    message: str


class FeedbackListResponse(BaseModel):
    """Paginated feedback list"""
    items: List[FeedbackBasic]
    total: int
    page: int
    page_size: int
    total_pages: int
