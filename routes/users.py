from fastapi import APIRouter, HTTPException, status, Depends, Request, Body
from db.dbconn import users_collections, groups, tasks, completedtasks, fs  # Assuming this is your database collection or function
from db.hash import Hash
from jose import jwt
from fastapi.encoders import jsonable_encoder
import os
from shemas.users import UserLogin, UserRegister, DeleteUserRequest, GroupCreateRequest, DeleteGroupRequest, UserEdit, GroupEdit, Task, TaskTime,TaskTimeCancel, TaskEdit, GroupCreateRequest2, GroupCreateRequest3, TaskRequest
from middelware.auth import auth_middleware_status_return, verify_admin_token, auth_middleware_phone_return
from bson import ObjectId
from io import BytesIO
from datetime import datetime
from datetime import datetime, timedelta
import calendar
from fastapi.responses import StreamingResponse
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from urllib.parse import unquote
from fastapi import Form, File, UploadFile, Request, Depends
from typing import List
import json
import gridfs

user_app = APIRouter()  # Correct instantiation of APIRouter

@user_app.post("/login")
async def login_user(user: UserLogin):
    found_user = await users_collections.find_one({"phone": user.phone})
    
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
async def register_user(request: Request, user: UserRegister):
    existing_user = await users_collections.find_one({"phone": user.phone})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    
    hashed_password = Hash.bcrypt(user.password)
    user.password = hashed_password

    try:
        await users_collections.insert_one(dict(user))
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is some problem with the database")
    
    return {"status": "Ok"}

@user_app.get("/task/{task_id}")
async def get_task(task_id: str):
    try:
        obj_id = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Невірний ID")

    task = await tasks.find_one({"_id": obj_id})
    if not task:
        raise HTTPException(status_code=404, detail="Завдання не знайдено")

    task["_id"] = str(task["_id"])
    return task
    
@user_app.post("/tasks_by_group")
async def get_tasks_by_group(start_date: str, end_date: str, phone=Depends(auth_middleware_phone_return)):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неправильний формат дати")

    query = {
        "phone": phone,
        "finish_time": {"$exists": True}
    }

    tasks_cursor = completedtasks.find(query)

    result = {}

    grouped_tasks = {}

    async for task in tasks_cursor:
        try:
            finish_time = datetime.strptime(task["finish_time"], "%d.%m.%Y, %H:%M:%S")
        except Exception:
            continue

        if start_dt <= finish_time <= end_dt:
            group = task.get("group", "Без групи")
            task["_id"] = str(task["_id"])
            task["__parsed_finish_time"] = finish_time  # временное поле для сортировки
            grouped_tasks.setdefault(group, []).append(task)

    # Сортировка внутри каждой группы по времени завершения (от нового к старому)
    for group, tasks in grouped_tasks.items():
        sorted_tasks = sorted(tasks, key=lambda x: x["__parsed_finish_time"], reverse=True)
        for t in sorted_tasks:
            del t["__parsed_finish_time"]  # удалим временное поле
            total_active_minutes = sum(t.get("active_minutes", 0) or 0 for t in sorted_tasks)

        result[group] = [total_active_minutes] + sorted_tasks
    print(result)
    return result

@user_app.post("/tasks_by_group2")
async def get_tasks_by_group(request: TaskRequest, phone=Depends(auth_middleware_phone_return)):
    try:
        phone_group = await groups.find_one({"group_name": request.group}, {"manager_phone": 1})
        if phone_group["manager_phone"] != phone:
            raise HTTPException(status_code=403, detail="У вас немає прав для виконання цієї задачі")
    except Exception:
        raise HTTPException(status_code=404, detail="Група не знайдена")
    try:
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неправильний формат дати")

    query = {
        "group": request.group,
        "finish_time": {"$exists": True}
    }

    tasks_cursor = completedtasks.find(query)

    result = []
    total_active_minutes = 0  # <- добавляем переменную для суммы

    async for task in tasks_cursor:
        try:
            finish_time = datetime.strptime(task["finish_time"], "%d.%m.%Y, %H:%M:%S")
        except Exception:
            continue

        if start_dt <= finish_time <= end_dt:
            task["_id"] = str(task["_id"])
            
            # Добавляем проверку и суммирование active_minutes
            active_minutes = task.get("active_minutes")
            if isinstance(active_minutes, (int, float)):
                total_active_minutes += active_minutes

            result.append(task)
    result2 = [total_active_minutes] + result
    print(result2)
    return result2

@user_app.get("/get_users", dependencies=[Depends(verify_admin_token)])
async def get_users(request: Request):
    cursor = users_collections.find({"status": {"$ne": "admin"}})
    users_list = []
    async for user in cursor:
        user["_id"] = str(user["_id"])
        users_list.append(user)
    return users_list

@user_app.post("/delete_user", dependencies=[Depends(verify_admin_token)])
async def delete_user(request: Request, user: DeleteUserRequest):
    if not ObjectId.is_valid(user.id):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    result = await users_collections.delete_one({"_id": ObjectId(user.id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    tasks_for_delete = []
    async for group in groups.find({"manager_phone": user.phone}, {'_id': 0, 'group_name': 1}):
        tasks_for_delete.append(group['group_name'])

    await groups.delete_many({"manager_phone": user.phone})
    await groups.update_many(
        {"user_phones": {"$in": [user.phone]}},
        {"$pull": {"user_phones": user.phone}}
    )
    await tasks.delete_many({'group': {"$in": tasks_for_delete}})

    return {"message": "User successfully deleted"}

@user_app.post("/delete_group", dependencies=[Depends(verify_admin_token)])
async def delete_group(request: Request, group: DeleteGroupRequest):
    result = await groups.delete_one({"group_name": group.group_name})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")

    await tasks.delete_many({'group': group.group_name})
    
    return {"message": "Group successfully deleted"}

@user_app.get("/get_users_add", dependencies=[Depends(verify_admin_token)])
async def get_users_add(request: Request):
    cursor = users_collections.find(
        {"status": {"$nin": ["admin", "receive"]}},
        {"name": 1, "phone": 1, "_id": 0}
    )
    
    return [user async for user in cursor]

@user_app.get("/get_users_receive", dependencies=[Depends(verify_admin_token)])
async def get_users_receive(request: Request):
    cursor = users_collections.find(
        {"status": {"$nin": ["admin", "add"]}},
        {"name": 1, "phone": 1, "_id": 0}
    )
    
    return [user async for user in cursor]

@user_app.post("/create_group/", dependencies=[Depends(verify_admin_token)])
async def create_group(group: GroupCreateRequest):
    existing_group = await groups.find_one({"group_name": group.group_name})
    if existing_group:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The group with this name already exists")

    group_data = {
        "group_name": group.group_name,
        "manager_phone": group.manager_phone,
        "user_phones": group.user_phones,
        "active": 1
    }
    await groups.insert_one(group_data)
    return {"message": "Group successfully created"}


@user_app.post("/get_users_info_group")
async def get_users_info_group(
    group: GroupCreateRequest2,
    phone: str = Depends(auth_middleware_phone_return)
):
    group_data = await groups.find_one({"group_name": group.group_name})
    if not group_data:
        raise HTTPException(status_code=404, detail="Group not found")
    if group_data["manager_phone"] != phone:
        raise HTTPException(status_code=403, detail="You do not have permission to access this group")
    user_phones = group_data.get("user_phones", [])
    cursor = users_collections.find({"phone": {"$in": user_phones}}, {"password": 0, "_id": 0, "status": 0})
    users = await cursor.to_list(length=None)  
    return {"users": users}

@user_app.post("/get_users_info_group2")
async def get_users_info_group2(
    groups_req: GroupCreateRequest3,
    phone: str = Depends(auth_middleware_phone_return)
):
    result = {}

    for group_name in groups_req.groups_names:
        group_data = await groups.find_one({"group_name": group_name})
        
        if not group_data:
            continue 
        
        if group_data["manager_phone"] != phone:
            continue  

        user_phones = group_data.get("user_phones", [])
        
        cursor = users_collections.find(
            {"phone": {"$in": user_phones}},
            {"password": 0, "_id": 0, "status": 0}
        )
        users = await cursor.to_list(length=None)
        
        result[group_name] = users
    
    return result
@user_app.get("/download_file/{file_id}")
async def download_file(file_id: str):
    # Преобразуем file_id в ObjectId
    try:
        file_object_id = ObjectId(file_id)  # Преобразование строки в ObjectId
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    # Поиск файла в GridFS по его ObjectId
    try:
        # Используем open_download_stream для асинхронного получения потока
        file_stream = await fs.open_download_stream(file_object_id)
    except gridfs.errors.NoFile:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Возвращаем файл пользователю как поток
    return StreamingResponse(file_stream, media_type="image/jpeg", headers={"Content-Disposition": f"attachment;"})

@user_app.get("/get_groups/", dependencies=[Depends(verify_admin_token)])
async def get_groups(request: Request):
    cursor = groups.find({}, {
        "group_name": 1,    
        "manager_phone": 1,  
        "user_phones": 1,
        "active": 1,
        "_id": 0     
    })
    return [group async for group in cursor] 

@user_app.post("/edit_user/", dependencies=[Depends(verify_admin_token)])
async def edit_user(request: Request, user: UserEdit):
    user_id = ObjectId(user.id)
    update_data = {}

    if user.name:
        update_data["name"] = user.name
    if user.password:
        update_data["password"] = Hash.bcrypt(user.password)
    if user.status is not None: 
        update_data["status"] = user.status
    if user.telegramName: 
        update_data["telegramName"] = user.telegramName

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    result = await users_collections.update_one(
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

    result = await groups.update_one(
        {"group_name": user.group_name},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")

    return {"message": "Group updated successfully"}
  
@user_app.get("/get_my_groups_analytic")
async def login_user(request: Request, start_date: str, end_date: str, phone = Depends(auth_middleware_phone_return)):
    print(start_date, end_date)
    
    # Получаем пользователей из группы
    users_group4 = await groups.find(
        {"active": 1},
        {"_id": 0, "group_name": 1, "user_phones": 1}
    ).to_list(length=None)
    print("==========", users_group4)
    users_group = {item["group_name"]: item["user_phones"] for item in users_group4}
    print(users_group)
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

    results = await tasks.aggregate(pipeline).to_list(length=None)
    
    groups_user = dict()
    for doc in results:
        e = list()
        e.append(doc['total_tasks'])
        groups_user[doc['_id']] = e
    
    # Преобразуем строки с датой в объекты datetime
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
    
    results = await completedtasks.aggregate(pipeline).to_list(length=None)
    
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
        d.append(int((total_count / groups_user[group][0]) * 100))
        d.append(int((1 - total_count / groups_user[group][0]) * 100)) 
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
    print(groups_user)
    for group in groups_user.keys():
        total_users = len(users_group[group]) * groups_user[group][0]
        if group in total_completed_tasks:
            total_completed_task = total_completed_tasks[group]['completed_tasks']
            total_not_in_time = total_completed_tasks[group]['not_in_time']
            compl_procent = int(total_completed_tasks[group]['completed_tasks'] / ((len(users_group[group]) * groups_user[group][0])) * 100)
            puncompl_procent = 100 - compl_procent
        else:
            total_completed_task = 0
            total_not_in_time = 0
            compl_procent = 0
            puncompl_procent = 100 
        groups_user[group].append(["Загалом", total_users, total_completed_task, total_not_in_time, compl_procent, puncompl_procent])
    
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

    current_row = 5

# Обработка данных из groups_data, пропускаем последнюю строку
    for group in groups_data[1:-1]:
        k = list()
        k.append(group[0])  # Добавляем имя группы
        k.append(groups_data[0])  # Добавляем заголовок (например, дату)
        k.extend(group[1:])  # Добавляем остальные данные
        ws.append(k)  # Добавляем строку
        current_row += 1  # Инкрементируем строку

    # Пропускаем последнюю строку, если она не является частью данных, которые нужно добавить в таблицу.
    # Просто добавляем её отдельно, чтобы не перезаписать информацию.
    ws.append(groups_data[-1])

    # Получаем последнюю строку
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
        for entry in group_data[1:-1]:
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
    # Асинхронный запрос для поиска групп, где текущий пользователь является менеджером
    results = await groups.find({"manager_phone": phone}, {"group_name": 1, "_id": 0}).to_list(length=None)
    results2 = [i["group_name"] for i in results]
    return results2


@user_app.get("/get_my_info")
async def get_info(request: Request, phone = Depends(auth_middleware_phone_return)):
    results = await users_collections.find({"phone": phone}, {"password": 0, "_id": 0}).to_list(length=None)
    re2 = list(results)
    print(re2)
    return jsonable_encoder(re2)

@user_app.post("/tasks")
async def create_task(request: Request, task: Task, phone=Depends(auth_middleware_phone_return)):
    result = await groups.find_one({"group_name": task.group}, {"manager_phone": 1, "_id": 0})
    user_info = await users_collections.find_one({'phone': phone}, {'name': 1})

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
            await tasks.insert_one(task_data)

        return {"message": f"{len(days_to_create)} tasks successfully saved to database"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save task: {str(e)}")


@user_app.get("/get_my_task")
async def get_tasks(request: Request, phone=Depends(auth_middleware_phone_return)):
    r = await groups.find({'user_phones': f"{phone}", 'active': 1}, {"group_name": 1, "_id": 0}).to_list(length=None)
    compltasks = await completedtasks.find({"phone": f"{phone}"}, {"id_task": 1, "_id": 0}).to_list(length=None)
    
    tasksCompleteIDs = [task['id_task'] for task in compltasks]
    
    groups_name = [group["group_name"] for group in r]
    tasks_cursor = tasks.find({'group': {'$in': groups_name}}).sort([('importance', -1)])
    user_tasks = await tasks_cursor.to_list(length=None)

    for task in user_tasks:
        task["_id"] = str(task["_id"])

    user_tasks.append(tasksCompleteIDs)
    print(user_tasks)
    return user_tasks

@user_app.post("/push_task")
async def push_task(
    start_time: str = Form(...),
    finish_time: str = Form(...),
    pause_start: str = Form(...),
    pause_end: str = Form(...),
    id_task: str = Form(...),
    group: str = Form(...),
    task_name: str = Form(...),
    keyTime: str = Form(...),
    comment: str = Form(None),
    in_time: int = Form(...),
    images: List[UploadFile] = File([]),
    phone=Depends(auth_middleware_phone_return)
):
    # Преобразуем паузы в списки
    pause_start_list = json.loads(pause_start)
    pause_end_list = json.loads(pause_end)

    # Конвертация строк в datetime
    try:
        dt_start = datetime.strptime(start_time, "%d.%m.%Y, %H:%M:%S")
        dt_finish = datetime.strptime(finish_time, "%d.%m.%Y, %H:%M:%S")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат времени")

    # Расчёт общего времени выполнения
    total_minutes = (dt_finish - dt_start).total_seconds() / 60

    # Расчёт времени всех пауз
    total_pause_minutes = 0
    for start_str, end_str in zip(pause_start_list, pause_end_list):
        try:
            ps = datetime.strptime(start_str, "%d.%m.%Y, %H:%M:%S")
            pe = datetime.strptime(end_str, "%d.%m.%Y, %H:%M:%S")
            total_pause_minutes += (pe - ps).total_seconds() / 60
        except Exception:
            continue

    active_minutes = total_minutes - total_pause_minutes

    # Загрузка фото в GridFS
    photo_refs = []
    for image in images:
        content = await image.read()
        file_id = await fs.upload_from_stream(image.filename, content)
        photo_refs.append({
            "file_id": str(file_id),
            "filename": image.filename
        })

    # Подготовка данных задачи
    task_data = {
        "start_time": start_time,
        "finish_time": finish_time,
        "pause_start": pause_start_list,
        "pause_end": pause_end_list,
        "id_task": id_task,
        "group": group,
        "keyTime": keyTime,
        "phone": phone,
        "comment": comment,
        "in_time": in_time,
        "task_name": task_name,
        "status": 1,
        "photos": photo_refs,
        "total_minutes": int(total_minutes),
        "pause_minutes": int(total_pause_minutes),
        "active_minutes": int(active_minutes)
    }

    await completedtasks.insert_one(task_data)

    return {"message": "Informations about task successfully saved to database"}
        


@user_app.post("/cancel_task")
async def cancel_task(request: Request, task_cancel: TaskTimeCancel, phone=Depends(auth_middleware_phone_return)):
    task_data = {
        "finish_time": task_cancel.cancel_time,
        "id_task": task_cancel.id_task,
        "phone": phone,
        "comment": task_cancel.comment,
        "group": task_cancel.group,
        "task_name": task_cancel.task_name,
        'status': 0
    }
    print(task_data)
    await completedtasks.insert_one(task_data)
    return {"message": "Informations about task successfully saved to database"}

@user_app.get("/get_my_created_task/")
async def get_created_tasks(request: Request, phone=Depends(auth_middleware_phone_return)):
    tasks_cursor = tasks.find({'created_by': phone}).sort([('importance', -1)])
    user_tasks = await tasks_cursor.to_list(length=None)

    for task in user_tasks:
        task["_id"] = str(task["_id"])

    print(user_tasks)
    return user_tasks


@user_app.get("/get_infoprocent_about_task/{group}/{task_id}")
async def get_info_procent_about_task(request: Request, group: str, task_id: str):
    task_id = unquote(task_id)
    print(task_id)
    count = await groups.find_one({'group_name': group})
    count2 = await completedtasks.find({'id_task': task_id, 'status': 1}).to_list(length=None)
    print(len(count2))
    return (len(count2)/len(count['user_phones'])) * 100
    
           

@user_app.delete("/delete_task/{task_id}")
async def delete_task(request: Request, task_id: str, phone=Depends(auth_middleware_phone_return)):
    result = await tasks.delete_one({"_id": ObjectId(task_id), 'created_by': phone})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="The task was not found or you do not have sufficient rights")
    
    return {"message": "Task successfully deleted"}


@user_app.put("/update_task/")
async def update_task(request: Request, task: TaskEdit, phone=Depends(auth_middleware_phone_return)):
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
        result = await tasks.update_one(
            {"_id": ObjectId(task.taskid), 'created_by': phone},
            {"$set": task_data}
        )
        
        if result.modified_count > 0:
            return {"message": "Task successfully updated"}
        else:
            raise HTTPException(status_code=404, detail="Failed to update task")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")
    
    




