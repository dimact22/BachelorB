# Import the googlemaps library and dotenv to load environment variables
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi import HTTPException, status
import re
from typing import Optional
from typing import List, Optional

# Model to represent a user's registration data
class UserLogin(BaseModel):
    phone: str = Field(..., min_length=13)
    password: str = Field(..., min_length=6, max_length=20)

class UserRegister(BaseModel):
    name: str
    phone: str = Field(..., min_length=13)
    password: str = Field(..., min_length=6, max_length=20)
    status: str
    telegramName: str

class UserEdit(BaseModel):
    id: str
    name: str
    status: str
    password: str
    telegramName: str

class GroupCreateRequest2(BaseModel):
    group_name: str

class GroupCreateRequest3(BaseModel):
    groups_names: List[str]

class DeleteUserRequest(BaseModel):
    id: str
    phone: str

class DeleteGroupRequest(BaseModel):
    group_name: str

class GroupCreateRequest(BaseModel):
    group_name: str  # Название группы
    manager_phone: str  # ID менеджера
    user_phones: List[str]  # Список пользователей
    
class GroupEdit(BaseModel):
    group_name: str  # Название группы
    manager_phone: str  # ID менеджера
    user_phones: List[str]  # Список пользователей
    active: int

class Task(BaseModel):
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

    
class TaskEdit(BaseModel):
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

class TaskRequest(BaseModel):
    start_date: str
    end_date: str
    group: str


class TaskTime(BaseModel):
    start_time: str
    finish_time: str
    pause_start: List[str]
    pause_end: List[str]
    id_task: str
    group: str
    keyTime: str
    comment: Optional[str] # type: ignore
    in_time: int
    
class TaskTimeCancel(BaseModel):
    cancel_time: str
    id_task: str
    task_name: str
    group: str
    comment: str

