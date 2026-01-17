# Import the googlemaps library and dotenv to load environment variables
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi import HTTPException, status
import re
from typing import Optional
from typing import List, Optional

class UserLogin(BaseModel):
    """
    Schema for user login credentials.
    
    Attributes:
        phone (str): User's phone number in international format (min 13 chars)
        password (str): User's password (6-20 chars)
        
    Example:
        {
            "phone": "+380123456789",
            "password": "mypassword123"
        }
    """
    phone: str = Field(..., min_length=13)
    password: str = Field(..., min_length=6, max_length=20)

class UserRegister(BaseModel):
    """
    Schema for user registration data.
    
    Attributes:
        name (str): Full name of the user
        phone (str): User's phone number in international format (min 13 chars)
        password (str): User's password (6-20 chars)
        status (str): User role/status (e.g., 'admin', 'user')
        telegramName (str): Telegram username
        
    Example:
        {
            "name": "Alice Smith",
            "phone": "+380987654321",
            "password": "securepass123",
            "status": "manager",
            "telegramName": "alice_smith"
        }
    """
    name: str
    phone: str = Field(..., min_length=13)
    password: str = Field(..., min_length=6, max_length=20)
    status: str
    telegramName: str

class UserEdit(BaseModel):
    """
    Schema for user editing.
    
    Attributes:
        id (str): MongoDB ObjectId of user to edit
        name (str): New name (optional)
        status (str): New status (optional)
        password (str): New password (optional)
        telegramName (str): New Telegram username (optional)
        
    Example:
        {
            "id": "507f1f77bcf86cd799439011",
            "name": "Updated Name",
            "status": "user",
            "password": "updatedpass123",
            "telegramName": "updated_tg"
        }
    """
    id: str
    name: str
    status: str
    password: str
    telegramName: str

class GroupCreateRequest2(BaseModel):
    """
    Schema for single group information request.
    
    Attributes:
        group_name (str): Name of group to query
        
    Example:
        {
            "group_name": "Development"
        }
    """
    group_name: str

class GroupCreateRequest3(BaseModel):
    """
    Schema for multiple groups information request.
    
    Attributes:
        groups_names (List[str]): List of group names to query
        
    Example:
        {
            "groups_names": ["Marketing", "Sales"]
        }
    """
    groups_names: List[str]

class DeleteUserRequest(BaseModel):
    """
    Schema for user deletion request.
    
    Attributes:
        id (str): MongoDB ObjectId of user to delete
        phone (str): User's phone number
        
    Example:
        {
            "id": "507f1f77bcf86cd799439011",
            "phone": "+380123456789"
        }
    """
    id: str
    phone: str

class DeleteGroupRequest(BaseModel):
    """
    Schema for group deletion request.
    
    Attributes:
        group_name (str): Name of group to delete
        
    Example:
        {
            "group_name": "Marketing"
        }
    """
    group_name: str

class GroupCreateRequest(BaseModel):
    """
    Schema for group creation.
    
    Attributes:
        group_name (str): Unique group name
        manager_phone (str): Phone of group manager
        user_phones (List[str]): List of member phones
        
    Example:
        {
            "group_name": "Design",
            "manager_phone": "+380123456789",
            "user_phones": ["+380987654321", "+380111223344"]
        }
    """
    group_name: str  
    manager_phone: str  
    user_phones: List[str]  
    
class GroupEdit(BaseModel):
    """
    Schema for group editing.
    
    Attributes:
        group_name (str): Name of group to edit
        manager_phone (str): New manager phone (optional)
        user_phones (List[str]): New list of member phones (optional)
        active (int): 1 for active, 0 for inactive
        
    Example:
        {
            "group_name": "Marketing",
            "manager_phone": "+380987654321",
            "user_phones": ["+380111223344"],
            "active": 0
        }
    """
    group_name: str  
    manager_phone: str  
    user_phones: List[str]  
    active: int

class Task(BaseModel):
    """
    Schema for task creation.
    
    Attributes:
        title (str): Task title
        description (str): Task description
        startDate (str): Start date (YYYY-MM-DD)
        endDate (str): End date (YYYY-MM-DD)
        startTime (str): Start time (HH:MM)
        endTime (str): End time (HH:MM)
        repeatDays (List[str]): Days of week for recurring tasks
        group (str): Task group name
        taskType (str): Task type ('general', 'weekly', or single)
        importance (int): Priority level (1-5)
        needphoto (int): 1 if photo required, 0 otherwise
        needcomment (int): 1 if comment required, 0 otherwise
        
    Example:
        {
            "title": "Code Review",
            "description": "Review PRs",
            "startDate": "2023-01-01",
            "endDate": "2023-01-01",
            "startTime": "15:00",
            "endTime": "16:00",
            "repeatDays": [],
            "group": "Development",
            "taskType": "single",
            "importance": 3,
            "needphoto": 0,
            "needcomment": 1
        }
    """
    title: str
    description: str
    startDate: str
    endDate: str
    startTime: str
    endTime: str
    repeatDays: List[str] = []
    group: str
    taskType: str
    importance: int
    needphoto: int
    needcomment: int
    openquestion: Optional[bool] = False

    
class TaskEdit(BaseModel):
    """
    Schema for task editing.
    
    Attributes:
        title (str): Updated title
        description (str): Updated description
        start_date (str): Updated start date (YYYY-MM-DD)
        end_date (str): Updated end date (YYYY-MM-DD)
        start_time (str): Updated start time (HH:MM)
        end_time (str): Updated end time (HH:MM)
        repeat_days (List[str]): Updated recurrence days
        group (str): Updated group name
        task_type (str): Updated task type
        importance (int): Updated priority (1-5)
        created_by (str): Creator phone (must match authenticated user)
        taskid (str): Task ID to update
        needphoto (int): 1 if photo required, 0 otherwise
        needcomment (int): 1 if comment required, 0 otherwise
        
    Example:
        {
            "title": "Updated Meeting",
            "description": "New agenda",
            "start_date": "2023-01-01",
            "end_date": "2023-01-01",
            "start_time": "14:00",
            "end_time": "15:00",
            "repeat_days": ["Monday"],
            "group": "Development",
            "task_type": "weekly",
            "importance": 3,
            "created_by": "+380123456789",
            "taskid": "507f1f77bcf86cd799439011",
            "needphoto": 0,
            "needcomment": 1
        }
    """
    title: str
    description: str
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    repeat_days: List[str] = []
    group: str
    task_type: str
    importance: int
    created_by: str
    taskid: str
    needphoto: int
    needcomment: int
    openquestion: Optional[bool] = False
    
class QuestionTaskRequest(BaseModel):
    taskId: str
    taskTitle: str
    comment: str
    createdBy: str
    createdName: str
    
class ChatReadRequest(BaseModel):
    task_id: str
    other_user_phone: str
        
class TaskRequest(BaseModel):
    """
    Schema for task retrieval request by group.
    
    Attributes:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        group (str): Group name to filter tasks
        
    Example:
        {
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "group": "Marketing"
        }
    """
    start_date: str
    end_date: str
    group: str


class TaskTime(BaseModel):
    """
    Schema for task completion time tracking.
    
    Attributes:
        start_time (str): Start time (DD.MM.YYYY, HH:MM:SS)
        finish_time (str): Finish time (DD.MM.YYYY, HH:MM:SS)
        pause_start (List[str]): List of pause start times
        pause_end (List[str]): List of pause end times
        id_task (str): Original task ID
        group (str): Task group name
        keyTime (str): Unique time key
        comment (Optional[str]): Completion comment
        in_time (int): 1 if completed on time, 0 otherwise
        
    Example:
        {
            "start_time": "01.01.2023,10:00:00",
            "finish_time": "01.01.2023,11:30:00",
            "pause_start": ["01.01.2023,10:30:00"],
            "pause_end": ["01.01.2023,10:45:00"],
            "id_task": "507f1f77bcf86cd799439011",
            "group": "Development",
            "keyTime": "unique123",
            "comment": "Completed with notes",
            "in_time": 1
        }
    """
    start_time: str
    finish_time: str
    pause_start: List[str]
    pause_end: List[str]
    id_task: str
    group: str
    keyTime: str
    comment: Optional[str] 
    in_time: int
    
class TaskTimeCancel(BaseModel):
    """
    Schema for task cancellation.
    
    Attributes:
        cancel_time (str): Cancellation timestamp (DD.MM.YYYY, HH:MM:SS)
        id_task (str): Original task ID
        task_name (str): Task name
        group (str): Group name
        comment (str): Cancellation reason
        
    Example:
        {
            "cancel_time": "01.01.2023,12:00:00",
            "id_task": "507f1f77bcf86cd799439011",
            "task_name": "Meeting",
            "group": "Development",
            "comment": "Conflict with other task"
        }
    """
    cancel_time: str
    id_task: str
    task_name: str
    group: str
    comment: str

