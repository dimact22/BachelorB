from fastapi import APIRouter, HTTPException, status, Depends, Request, Body
from db.dbconn import users_collections, groups, tasks, completedtasks  # Assuming this is your database collection or function
from db.hash import Hash
from jose import jwt
from fastapi.encoders import jsonable_encoder
import os
from shemas.users import UserLogin, UserRegister, DeleteUserRequest, GroupCreateRequest, DeleteGroupRequest, UserEdit, GroupEdit, Task, TaskTime,TaskTimeCancel, TaskEdit
from middelware.auth import auth_middleware_status_return, verify_admin_token, auth_middleware_phone_return
from bson import ObjectId
from datetime import datetime
from fastapi.responses import StreamingResponse
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from urllib.parse import unquote

user_app = APIRouter()  # Correct instantiation of APIRouter

@user_app.post("/login")
async def login_user(user: UserLogin):
    """
    Login user: Authenticates and returns a JWT token.
    """
    
    found_user = users_collections.find_one({"phone": user.phone})  # Access your DB here
    
    if not found_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    
    if Hash.verify(user.password, found_user["password"]):
        token = jwt.encode({'sub': found_user["phone"], 'status': found_user['status']}, os.getenv("SecretJwt"), algorithm='HS256')
        return {"token": token}
    else:
        raise HTTPException(status_code=400, detail="Invalid credentials")

@user_app.get("/get_status/{token}")
async def login_user(token:str):
    payload = jwt.decode(token, os.getenv("SecretJwt"), algorithms=["HS256"])
    return str(payload.get("status"))

@user_app.post("/register", dependencies=[Depends(verify_admin_token)])
async def login_user(request: Request, user: UserRegister):
    existing_user = users_collections .find_one({"phone": user.phone}) # Check if the email already exists in the database
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists") # Return error if user exists
    hashed_password = Hash.bcrypt(user.password) # Hash the password for security
    user.password = hashed_password   
    try:
        users_collections.insert_one(dict(user)) # Insert new user into database
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="There is some problem with the database, please try again later")
    return {"status": "Ok"} # Return success message and token

@user_app.get("/get_users", dependencies=[Depends(verify_admin_token)])
async def get_users(request: Request):
    users = users_collections.find({"status": {"$ne": "admin"}})
    # Преобразуем _id в строку для каждого документа
    users_list = []
    for user in users:
        user["_id"] = str(user["_id"])  # Преобразуем _id в строку
        users_list.append(user)
    return users_list

@user_app.post("/delete_user", dependencies=[Depends(verify_admin_token)])
async def delete_user(request: Request, user: DeleteUserRequest):
    # Проверяем валидность ObjectId
    if not ObjectId.is_valid(user.id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    result = users_collections.delete_one({"_id": ObjectId(user.id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    tasks_for_delete = [i['group_name'] for i in groups.find({"manager_phone": user.phone}, {'_id':0, 'group_name':1})]
    
    
    print(tasks_for_delete)
    groups.delete_many({"manager_phone": user.phone})
    groups.update_many(
    {"user_phones": {"$in": [user.phone]}},  # Условие для поиска документов
    {"$pull": {"user_phones": user.phone}}   # Удаление телефона из массива   
)
    tasks.delete_many({'group':{"$in": [tasks_for_delete]}})
    
    return {"message": "User successfully deleted"}

@user_app.post("/delete_group", dependencies=[Depends(verify_admin_token)])
async def delete_group(request: Request, group: DeleteGroupRequest):
    
    result = groups.delete_one({"group_name": group.group_name})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")

    tasks.delete_many({'group': group.group_name})
    
    return {"message": "Group successfully deleted"}

@user_app.get("/get_users_add", dependencies=[Depends(verify_admin_token)])
async def get_users_add(request: Request):
    users = users_collections.find(
        {
        "status": { "$nin": ["admin", "receive"] } 
        },
        {
            "name": 1,    
            "phone": 1,  
            "_id": 0     
        }
        );   
    users = list(users)
    return users 

@user_app.get("/get_users_receive", dependencies=[Depends(verify_admin_token)])
async def get_users_receive(request: Request):
    users = users_collections.find(
        {
        "status": { "$nin": ["admin", "add"] } 
        },
        {
            "name": 1,    
            "phone": 1,  
            "_id": 0     
        }
        );   
    users = list(users)
    return users 

@user_app.post("/create_group/", dependencies=[Depends(verify_admin_token)])
async def create_group(group: GroupCreateRequest):
    existing_group = groups.find_one({"group_name": group.group_name}) # Check if the email already exists in the database
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The group with this name already exists") # Return error if user exists
    group_data = {
        "group_name": group.group_name,
        "manager_phone": group.manager_phone,
        "user_phones": group.user_phones,
        "active": 1
    }
    groups.insert_one(group_data)
    return {"message": "Group successfully created"}

@user_app.get("/get_groups/", dependencies=[Depends(verify_admin_token)])
async def get_groups(request: Request):
    groups_all = groups.find({}, {
            "group_name": 1,    
            "manager_phone": 1,  
            "user_phones": 1,
            "active": 1,
            "_id": 0     
        })
    return list(groups_all)

@user_app.post("/edit_user/", dependencies=[Depends(verify_admin_token)])
async def edit_user(request: Request, user: UserEdit):
    user_id = ObjectId(user.id)  # Если у вас поле '_id' в MongoDB, то используйте ObjectId
    update_data = {}

    if user.name:
        update_data["name"] = user.name
    if user.password:
        update_data["password"] = Hash.bcrypt(user.password)
    if user.status is not None: 
        update_data["status"] = user.status

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    result = users_collections.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated successfully"}    

@user_app.post("/edit_group/", dependencies=[Depends(verify_admin_token)])
async def edit_group(request: Request, user: GroupEdit):
    update_data = {}

    if user.manager_phone:
        update_data["manager_phone"] = user.manager_phone
    if user.user_phones:
        update_data["user_phones"] = user.user_phones
    update_data["active"] = user.active
   
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    result = groups.update_one(
        {"group_name": user.group_name},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")

    return {"message": "Group updated successfully"}  
  
@user_app.get("/get_my_groups_analytic")
async def login_user(request: Request, start_date: str, end_date: str, phone = Depends(auth_middleware_phone_return)):
    print(start_date, end_date)
    users_group4 = groups.find(
    {"active": 1},
    {"_id": 0, "group_name": 1, "user_phones": 1}
    )
    users_group = {item["group_name"]: item["user_phones"] for item in users_group4}
    groups_user2 = dict()
# Подсчёт количества документов
    pipeline = [
    {
        "$match": {
            "created_by": phone,
            "end_date": {  # Фильтрация по диапазону дат
                "$gte": start_date,  # Дата окончания задачи должна быть больше или равна start_date
                "$lte": end_date  # Дата окончания задачи должна быть меньше или равна end_date
            }
        }
    },
    {
        "$group": {
            "_id": "$group",  # группируем по названию группы
            "total_tasks": { "$sum": 1 }
        }
    },
    {
        "$sort": { "total_tasks": -1 }  # сортируем по убыванию
    }
]

    results = list(tasks.aggregate(pipeline))
    groups_user = dict()
    for doc in results:
        e = list()
        e.append(doc['total_tasks'])
        groups_user[doc['_id']] = e
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = datetime.combine(start_date, datetime.min.time())  # Начало дня
    end_date = datetime.combine(end_date, datetime.max.time())
    pipeline = [
    {
        "$match": {
            "status": 1,  # Задачи со статусом 1
        }
    },
    {
        "$addFields": {
            "finish_time_parsed": {
                "$dateFromString": {
                    "dateString": "$finish_time",  # Ваша строка с датой
                    "format": "%d.%m.%Y, %H:%M:%S"  # Формат строки, которую вы хотите преобразовать
                }
            }
        }
    },
    {
        "$match": {
            "finish_time_parsed": {
                "$gte": start_date,  # Сравниваем с начальной датой
                "$lt": end_date      # Сравниваем с конечной датой
            }
        }
    },
    {
        "$group": {
            "_id": {
                "group": "$group",  # Группируем по группе
                "phone": "$phone"   # Группируем по телефону
            },
            "total_count": { "$sum": 1 },  # Считаем общее количество
            "in_time_1_count": {
                "$sum": {
                    "$cond": [{ "$eq": ["$in_time", 1] }, 1, 0]  # Считаем задачи с in_time == 1
                }
            },
            "in_time_0_count": {
                "$sum": {
                    "$cond": [{ "$eq": ["$in_time", 0] }, 1, 0]  # Считаем задачи с in_time == 0
                }
            }
        }
    },
    {
        "$sort": {
            "_id.group": 1,  # Сортируем по группе
            "_id.phone": 1   # Сортируем по телефону
        }
    }
]
    total_count_group = dict()
    total_completed_tasks = dict()
    results = list(completedtasks.aggregate(pipeline))
    for result in results:
        d = list()
        group = result["_id"]["group"]
        phone = result["_id"]["phone"]
        total_count = result["total_count"]
        total_count_group[group] = total_count
        in_time_1_count = result["in_time_1_count"]
        in_time_0_count = result["in_time_0_count"]
        if group not in total_completed_tasks:
            total_completed_tasks[group] = dict()
        if 'completed_tasks' not in total_completed_tasks[group]:
            total_completed_tasks[group]['completed_tasks'] = 0
        if 'not_in_time' not in total_completed_tasks[group]:
            total_completed_tasks[group]['not_in_time'] = 0
        total_completed_tasks[group]['completed_tasks'] += total_count
        total_completed_tasks[group]['not_in_time'] += in_time_0_count
        d.append(phone)
        d.append(total_count)
        d.append(in_time_0_count)
        d.append(int((total_count/groups_user[group][0])*100))
        d.append(int((1 - total_count/groups_user[group][0])*100)) 
        groups_user[group].append(d)         
        if group not in groups_user2:
            groups_user2[group] = []
        groups_user2[group].append(phone)
    for group in groups_user.keys():
        all_phones = set(users_group[group])
        if group in groups_user2:
            selected_phones = set(groups_user2[group])
        else:
            selected_phones = set()
        diff = all_phones - selected_phones
        for phone in diff:
            d = list()
            d.append(phone)
            d.append(0)
            d.append(0)
            d.append(0)
            d.append(100) 
            groups_user[group].append(d)
    for group in groups_user.keys():
        total_users = len(users_group[group]) * groups_user[group][0]
        total_completed_task = total_completed_tasks[group]['completed_tasks']
        total_not_in_time = total_completed_tasks[group]['not_in_time']
        compl_procent = int(total_completed_tasks[group]['completed_tasks']/((len(users_group[group]) * groups_user[group][0]))*100)
        puncompl_procent = 100 - compl_procent
        groups_user[group].append(["Загалом", total_users, total_completed_task, total_not_in_time, compl_procent, puncompl_procent])
    print(groups_user)
    return groups_user

@user_app.post("/download_excel_tasks_analytic")
async def download_excel(start_date: str, end_date: str, group: str, groups_data: list = Body(...),  phone=Depends(auth_middleware_phone_return)):
    print(groups_data)
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Виконані завдання"

    # Заголовок с датами
    ws.merge_cells('A1:F1')
    cell = ws['A1']
    cell.value = f"{start_date} - {end_date}"
    cell.font = Font(bold=True, size=14)
    cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.append([])  # Пустая строка

    # Заголовки таблицы (строка 3)
    ws['A3'] = group
    ws['B3'] = "Задачі"
    ws.merge_cells("B3:D3")  # Объединяем ячейки для Телефон
    ws['E3'] = "Результат"
    ws.merge_cells("E3:F3")  # Объединяем ячейки для Задания

    # Стили для заголовков
    green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
    border_style = Border(
        left=Side(border_style="thin", color="000000"),
        right=Side(border_style="thin", color="000000"),
        top=Side(border_style="thin", color="000000"),
        bottom=Side(border_style="thin", color="000000")
    )

    # Применяем стили и границы для заголовков
    for col in ['A3', 'B3', 'E3']:
        cell = ws[col]
        cell.fill = green_fill
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_style

    data_header = ["Користувач", "Поставлено", "Виконано", "Невчасно", "% Виконання", "% Невиконання"]
    ws.append(data_header)  # Добавляем строку с заголовками данных

    # Применяем зелёный цвет и границы для заголовков данных
    for col_num, cell_value in enumerate(data_header, start=1):
        cell = ws.cell(row=4, column=col_num)
        cell.fill = green_fill
        cell.font = Font(bold=True)
        cell.border = border_style

    # Обработка данных из группы
    for group in groups_data[1:-2]:
        k = list()
        k.append(group[0])
        k.append(groups_data[0])
        k.extend(group[1:])
        ws.append(k)
    ws.append(groups_data[-1])
    last_row = ws.max_row

# Применяем стили к последней строке
    for col in range(1, len(groups_data[-1]) + 1):
        cell = ws.cell(row=last_row, column=col)
        cell.fill = green_fill
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_style
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tasks_report.xlsx"}
    )

@user_app.post("/download_excel_tasks_analytic2")
async def download_excel_multiple_groups(
    start_date: str,
    end_date: str,
    groups: list = Body(...),
    groups_data: dict = Body(...),
    phone=Depends(auth_middleware_phone_return)
):
    print(groups_data)
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Звіт по задачах"

    # Заголовок с датами
    ws.merge_cells('A1:F1')
    cell = ws['A1']
    cell.value = f"{start_date} - {end_date}"
    cell.font = Font(bold=True, size=14)
    cell.alignment = Alignment(horizontal="center", vertical="center")

    current_row = 3  # Начиная со строки 3 (после заголовка и пустой строки)

    # Стили
    green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
    light_blue_fill = PatternFill(start_color="FFE1F5FE", end_color="FFE1F5FE", fill_type="solid")
    border_style = Border(
        left=Side(border_style="thin", color="000000"),
        right=Side(border_style="thin", color="000000"),
        top=Side(border_style="thin", color="000000"),
        bottom=Side(border_style="thin", color="000000")
    )

    for group in groups:
        group_data = groups_data.get(group, [])
        if not group_data:
            continue

        # Название группы
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=6)
        cell = ws.cell(row=current_row, column=1)
        cell.value = group
        cell.fill = light_blue_fill
        cell.font = Font(bold=True, size=12)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in range(1, 7):  
            border_cell = ws.cell(row=current_row, column=col)
            border_cell.border = border_style
        current_row += 1

        # Подзаголовки
        header1 = ["Користувач", "Поставлено", "Виконано", "Невчасно", "% Виконання", "% Невиконання"]
        for col_num, header in enumerate(header1, start=1):
            cell = ws.cell(row=current_row, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = green_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_style
        current_row += 1

        # Данные по пользователям
        for entry in group_data[1:-2]:
            row_data = [entry[0], group_data[0], entry[1], entry[2], entry[3], entry[4]]
            for col_num, value in enumerate(row_data, start=1):
                cell = ws.cell(row=current_row, column=col_num)
                cell.value = value
                cell.border = border_style
            current_row += 1
        # Добавляем последнюю строку отдельно
        last_entry = group_data[-1]
        last_row_data = [last_entry[0], last_entry[1], last_entry[2], last_entry[3], last_entry[4], last_entry[5]]

        for col_num, value in enumerate(last_row_data, start=1):
            cell = ws.cell(row=current_row, column=col_num)
            cell.value = value
            cell.fill = green_fill  # применяем стили
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_style
        current_row += 1

    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tasks_report_multiple.xlsx"}
    )
    


@user_app.get("/get_my_groups")
async def login_user(request: Request, phone = Depends(auth_middleware_phone_return)):
    results = groups.find({"manager_phone": phone}, {"group_name": 1, "_id": 0}) 
    results2 = list()
    for i in results:
        results2.append(i["group_name"])
    start_date = "2025-05-01"
    end_date = "2025-05-10"

# Подсчёт количества документов
    pipeline = [
    {
        "$match": {
            "created_by": phone
        }
    },
    {
        "$group": {
            "_id": "$group",  # группируем по названию группы
            "total_tasks": { "$sum": 1 }
        }
    },
    {
        "$sort": { "total_tasks": -1 }  # сортируем по убыванию
    }
]

    results = list(tasks.aggregate(pipeline))
    groups_user = dict()
    for doc in results:
        e = list()
        e.append(doc['total_tasks'])
        groups_user[doc['_id']] = e
    start_date = datetime.strptime("2025-05-01", "%Y-%m-%d")
    end_date = datetime.strptime("2025-05-10", "%Y-%m-%d")
    start_date = datetime.combine(start_date, datetime.min.time())  # Начало дня
    end_date = datetime.combine(end_date, datetime.max.time())
    print(start_date, end_date)
    pipeline = [
    {
        "$match": {
            "status": 1,  # Задачи со статусом 1
        }
    },
    {
        "$addFields": {
            "finish_time_parsed": {
                "$dateFromString": {
                    "dateString": "$finish_time",  # Ваша строка с датой
                    "format": "%d.%m.%Y, %H:%M:%S"  # Формат строки, которую вы хотите преобразовать
                }
            }
        }
    },
    {
        "$match": {
            "finish_time_parsed": {
                "$gte": start_date,  # Сравниваем с начальной датой
                "$lt": end_date      # Сравниваем с конечной датой
            }
        }
    },
    {
        "$group": {
            "_id": {
                "group": "$group",  # Группируем по группе
                "phone": "$phone"   # Группируем по телефону
            },
            "total_count": { "$sum": 1 },  # Считаем общее количество
            "in_time_1_count": {
                "$sum": {
                    "$cond": [{ "$eq": ["$in_time", 1] }, 1, 0]  # Считаем задачи с in_time == 1
                }
            },
            "in_time_0_count": {
                "$sum": {
                    "$cond": [{ "$eq": ["$in_time", 0] }, 1, 0]  # Считаем задачи с in_time == 0
                }
            }
        }
    },
    {
        "$sort": {
            "_id.group": 1,  # Сортируем по группе
            "_id.phone": 1   # Сортируем по телефону
        }
    }
]
    print(groups_user['Грурра тест последний'][0])
    # Выполнение агрегации
    results = list(completedtasks.aggregate(pipeline))
    for result in results:
        d = list()
        group = result["_id"]["group"]
        phone = result["_id"]["phone"]
        total_count = result["total_count"]
        in_time_1_count = result["in_time_1_count"]
        in_time_0_count = result["in_time_0_count"]
        d.append(phone)
        d.append(total_count)
        d.append(in_time_0_count)
        d.append(int((total_count/groups_user[group][0])*100))
        d.append(int((1 - total_count/groups_user[group][0])*100))          
        groups_user[group].append(d)
    print(groups_user)
    return results2  

@user_app.get("/get_my_info")
async def get_info(request: Request, phone = Depends(auth_middleware_phone_return)):
    results = users_collections.find({"phone": phone},{"password": 0, "_id": 0}) 
    re2 = list()
    for i in results:
        re2.append(i)
    print(re2)
    return jsonable_encoder(re2)

from datetime import datetime, timedelta
import calendar

@user_app.post("/tasks")
async def create_task(request: Request, task: Task, phone=Depends(auth_middleware_phone_return)):
    result = groups.find_one({"group_name": task.group}, {"manager_phone": 1, "_id": 0})
    user_info = users_collections.find_one({'phone': phone}, {'name': 1})

    if not result or result["manager_phone"] != phone:
        raise HTTPException(status_code=404, detail="У вас немає прав для виконання цієї задачі")

    if not user_info:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    try:
        task_type = task.taskType
        start_date = datetime.strptime(task.startDate, "%Y-%m-%d")
        end_date = datetime.strptime(task.endDate, "%Y-%m-%d")

        days_to_create = []

        if task_type == "general":
            current = start_date
            while current <= end_date:
                days_to_create.append(current)
                current += timedelta(days=1)

        elif task_type == "weekly":
            repeat_days = task.repeatDays  # example: ["Monday", "Wednesday"]
            weekday_indices = [list(calendar.day_name).index(day) for day in repeat_days]

            current = start_date
            while current <= end_date:
                if current.weekday() in weekday_indices:
                    days_to_create.append(current)
                current += timedelta(days=1)

        else:
            # Одноразовое задание
            days_to_create = [start_date]

        for day in days_to_create:
            task_data = {
                "title": task.title,
                "description": task.description,
                "start_date": day.strftime("%Y-%m-%d"),
                "end_date": day.strftime("%Y-%m-%d"),
                "start_time": task.startTime,
                "end_time": task.endTime,
                "repeat_days": task.repeatDays,
                "group": task.group,
                "task_type": task.taskType,
                "importance": int(task.importance),
                "created_by": phone,
                'needphoto': task.needphoto,
                'needcomment': task.needcomment,
                "created_name": user_info['name']
            }
            tasks.insert_one(task_data)

        return {"message": f"{len(days_to_create)} tasks successfully saved to database"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save task: {str(e)}")


@user_app.get("/get_my_task")
async def get_tasks(request: Request, phone=Depends(auth_middleware_phone_return)):
    r = groups.find({'user_phones': f"{phone}", 'active': 1},{"group_name": 1, "_id": 0})
    compltasks = completedtasks.find({"phone": f"{phone}"}, {"id_task": 1, "_id": 0})
    tasksCompleteIDs = []
    for i in compltasks:
        tasksCompleteIDs.append(i['id_task'])
    
    groups_name = []
    for i in r:
        groups_name.append(i["group_name"])
    tasks_cursor = tasks.find(
    {'group': {'$in': groups_name}}).sort([('importance', -1)])
    user_tasks = list(tasks_cursor)
    for i in range(0,len(user_tasks)):
        user_tasks[i]["_id"] = str(user_tasks[i]["_id"])    
    user_tasks.append(tasksCompleteIDs)
    print(user_tasks)
    return user_tasks

@user_app.post("/push_task")
async def login_user(request: Request, task: TaskTime, phone = Depends(auth_middleware_phone_return)):
    task_data = {
        "start_time": task.start_time,
        "finish_time": task.finish_time,
        "pause_start": task.pause_start,
        "pause_end": task.pause_end,
        "id_task": task.id_task,
        'group': task.group,
        "phone": phone,
        "comment": task.comment,
        'status': 1,
        'in_time': task.in_time
    }   
    completedtasks.insert_one(task_data)
    return {"message": "Informations about task successfully saved to database"}

@user_app.post("/cancel_task")
async def login_user(request: Request, task_cancel: TaskTimeCancel, phone = Depends(auth_middleware_phone_return)):
    task_data = {
        "cancel_time": task_cancel.cancel_time,
        "id_task": task_cancel.id_task,
        "key_time": task_cancel.keyTime,
        "phone": phone,
        "comment": task_cancel.comment,
        'status': 0
    }   
    completedtasks.insert_one(task_data)
    return {"message": "Informations about task successfully saved to database"}

@user_app.get("/get_my_created_task/")
async def get_tasks(request: Request, phone=Depends(auth_middleware_phone_return)):
    tasks_cursor = tasks.find(
    {'created_by': phone}).sort([('importance', -1)])
    user_tasks = list(tasks_cursor)
    for i in range(0,len(user_tasks)):
        user_tasks[i]["_id"] = str(user_tasks[i]["_id"])    
    print(user_tasks)
    return user_tasks

@user_app.get("/get_infoprocent_about_task/{group}/{task_id}")
async def get_tasks(request: Request, group: str, task_id: str):
    task_id = unquote(task_id)
    print(task_id)
    count = groups.find_one(
    {'group_name': group}) 
    count2 = list(completedtasks.find({'key_time': task_id, 'status': 1}))
    print(len(count2))
    return (len(count2)/len(count['user_phones'])) * 100
    
           

@user_app.delete("/delete_task/{task_id}")
async def delete_group(request: Request, task_id: str, phone=Depends(auth_middleware_phone_return)):
    result = tasks.delete_one({"_id": ObjectId(task_id), 'created_by':phone})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="The task was not found or you do not have sufficient rights")
    
    return {"message": "Group successfully deleted"}

@user_app.put("/update_task/")
async def change_task(request: Request, task: TaskEdit, phone = Depends(auth_middleware_phone_return)):
    task_data = {
        "title": task.title,
        "description": task.description,
        "start_date": task.start_date,
        "end_date": task.end_date,
        "start_time": task.start_time,
        "end_time": task.end_time,
        "repeat_days": task.repeat_days,
        "group": task.group,
        "task_type": task.task_type,
        "importance": task.importance,
        'needcomment': task.needcomment,
        'needphoto': task.needphoto
    }
    try:
        result = tasks.update_one(
            {"_id": ObjectId(task.taskid), 'created_by':phone},  
            {"$set": task_data}  
        )
        
        if result:
            return {"message": "Group successfully updated"}
        else:
            raise HTTPException(status_code=404, detail=f"Failed to update task to database: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to update task to database: {str(e)}")
    
    




