from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, File, UploadFile, Form
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import InputPeerUser, InputPeerChannel
from loguru import logger
from pydantic import BaseModel
from typing import Optional, List, Union
import asyncio

from .config import settings
from .auth import create_client, check_authorized, login_with_phone, login_with_code, login_with_password, get_me

app = FastAPI(title="Telegram User API", description="API для отправки сообщений через личный аккаунт Telegram")
security = HTTPBasic()

# Хранилище клиентов
clients = {}

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Проверка базовой HTTP аутентификации"""
    is_correct_username = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    is_correct_password = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

async def get_client():
    """Получить экземпляр клиента Telegram"""
    if "client" not in clients:
        client = await create_client()
        clients["client"] = client
        await client.connect()
    return clients["client"]

# Модели данных
class PhoneNumber(BaseModel):
    phone: str

class VerificationCode(BaseModel):
    phone: str
    code: str
    phone_code_hash: str

class Password(BaseModel):
    password: str

class Message(BaseModel):
    recipient: str  # username, phone или chat_id
    text: str
    parse_mode: Optional[str] = None

class MediaMessage(BaseModel):
    recipient: str
    caption: Optional[str] = None

# Маршруты для авторизации
@app.get("/status", tags=["Auth"])
async def check_status(username: str = Depends(get_current_username)):
    """Проверить статус авторизации в Telegram"""
    client = await get_client()
    authorized = await check_authorized(client)
    if authorized:
        me = await get_me(client)
        return {"authorized": True, "user": me}
    return {"authorized": False}

@app.post("/login/send_code", tags=["Auth"])
async def send_code(phone_data: PhoneNumber, username: str = Depends(get_current_username)):
    """Отправить код подтверждения на телефон"""
    client = await get_client()
    result = await login_with_phone(client, phone_data.phone)
    return result

@app.post("/login/verify_code", tags=["Auth"])
async def verify_code(verification_data: VerificationCode, username: str = Depends(get_current_username)):
    """Подтвердить код из SMS"""
    client = await get_client()
    result = await login_with_code(
        client, 
        verification_data.phone, 
        verification_data.code, 
        verification_data.phone_code_hash
    )
    return result

@app.post("/login/2fa", tags=["Auth"])
async def verify_password(password_data: Password, username: str = Depends(get_current_username)):
    """Подтвердить двухфакторную аутентификацию паролем"""
    client = await get_client()
    result = await login_with_password(client, password_data.password)
    return result

# Маршруты для отправки сообщений
@app.post("/send/text", tags=["Messages"])
async def send_text_message(message: Message, username: str = Depends(get_current_username)):
    """Отправить текстовое сообщение"""
    client = await get_client()
    
    if not await check_authorized(client):
        raise HTTPException(status_code=401, detail="Не авторизован в Telegram")
    
    try:
        # Определение типа получателя (username, phone или chat_id)
        recipient = message.recipient
        entity = None
        
        # Если это числовой ID
        if recipient.isdigit():
            entity = int(recipient)
        # Если это username
        elif recipient.startswith("@"):
            entity = recipient
        # Если это номер телефона
        elif recipient.startswith("+"):
            entity = await client.get_entity(recipient)
        else:
            # Попробовать получить по имени без @
            try:
                entity = await client.get_entity(recipient)
            except Exception:
                raise HTTPException(status_code=404, detail=f"Получатель '{recipient}' не найден")
        
        # Отправка сообщения
        sent_message = await client.send_message(
            entity=entity,
            message=message.text,
            parse_mode=message.parse_mode
        )
        
        return {
            "status": "success",
            "message_id": sent_message.id,
            "date": sent_message.date.isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке сообщения: {str(e)}")

@app.post("/send/file", tags=["Messages"])
async def send_file(
    recipient: str = Form(...),
    caption: Optional[str] = Form(None),
    file: UploadFile = File(...),
    username: str = Depends(get_current_username)
):
    """Отправить файл или изображение"""
    client = await get_client()
    
    if not await check_authorized(client):
        raise HTTPException(status_code=401, detail="Не авторизован в Telegram")
    
    try:
        # Сохранение временного файла
        temp_file = f"/tmp/{file.filename}"
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Определение получателя
        entity = None
        if recipient.isdigit():
            entity = int(recipient)
        elif recipient.startswith("@"):
            entity = recipient
        elif recipient.startswith("+"):
            entity = await client.get_entity(recipient)
        else:
            try:
                entity = await client.get_entity(recipient)
            except Exception:
                raise HTTPException(status_code=404, detail=f"Получатель '{recipient}' не найден")
        
        # Отправка файла
        sent_message = await client.send_file(
            entity=entity,
            file=temp_file,
            caption=caption
        )
        
        # Удаление временного файла
        os.remove(temp_file)
        
        return {
            "status": "success",
            "message_id": sent_message.id,
            "date": sent_message.date.isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке файла: {str(e)}")

@app.get("/contacts", tags=["Contacts"])
async def get_contacts(username: str = Depends(get_current_username)):
    """Получить список контактов"""
    client = await get_client()
    
    if not await check_authorized(client):
        raise HTTPException(status_code=401, detail="Не авторизован в Telegram")
    
    try:
        contacts = []
        async for dialog in client.iter_dialogs():
            contact = {
                "id": dialog.id,
                "name": dialog.name,
                "type": "channel" if dialog.is_channel else "group" if dialog.is_group else "user"
            }
            
            if hasattr(dialog.entity, 'username') and dialog.entity.username:
                contact["username"] = dialog.entity.username
                
            contacts.append(contact)
        
        return {"contacts": contacts}
    except Exception as e:
        logger.error(f"Ошибка при получении контактов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении контактов: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    client = await create_client()
    clients["client"] = client
    await client.connect()
    logger.info("API сервер запущен")

@app.on_event("shutdown")
async def shutdown_event():
    """Завершение работы при остановке"""
    if "client" in clients:
        await clients["client"].disconnect()
    logger.info("API сервер остановлен")
