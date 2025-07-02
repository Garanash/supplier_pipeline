import os
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import sqlite3
import aiosqlite
from pathlib import Path

from .database import init_db, get_db
from .models import (
    User, UserInDB, UserCreate, Token, TokenData,
    Article, Supplier, EmailTemplate, SentEmail
)
from .auth import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
)
from .search import search_suppliers
from .email import send_email, get_email_templates
from .analytics import get_analytics_data

app = FastAPI()

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# Инициализация базы данных
@app.on_event("startup")
async def startup_event():
    await init_db()
    await create_test_user()


# Создание тестового пользователя
async def create_test_user():
    async with aiosqlite.connect("suppliers.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (username, email, hashed_password, is_active) VALUES (?, ?, ?, ?)",
            ("User", "user@example.com", get_password_hash("pass123"), True)
        )
        await db.commit()


# Маршруты аутентификации
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...)
):
    try:
        user = await authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid credentials")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )

        response = templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "username": user.username,
                "articles": [],
                "suppliers": []
            }
        )
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
        return response
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": str(e)}
        )


# Основные маршруты
@app.get("/", response_class=HTMLResponse)
async def dashboard(
        request: Request,
        current_user: User = Depends(get_current_active_user)
):
    async with aiosqlite.connect("suppliers.db") as db:
        cursor = await db.execute("SELECT * FROM articles WHERE user_id = ?", (current_user.id,))
        articles = await cursor.fetchall()

        cursor = await db.execute("""
            SELECT s.* FROM suppliers s
            JOIN articles a ON s.article_id = a.id
            WHERE a.user_id = ?
        """, (current_user.id,))
        suppliers = await cursor.fetchall()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": current_user.username,
            "articles": articles,
            "suppliers": suppliers
        }
    )


@app.post("/add_article", response_class=HTMLResponse)
async def add_article(
        request: Request,
        article_code: str = Form(...),
        current_user: User = Depends(get_current_active_user)
):
    async with aiosqlite.connect("suppliers.db") as db:
        await db.execute(
            "INSERT INTO articles (code, user_id) VALUES (?, ?)",
            (article_code, current_user.id)
        )
        await db.commit()

    return await dashboard(request, current_user)


@app.post("/search_suppliers/{article_id}", response_class=HTMLResponse)
async def search_suppliers_for_article(
        request: Request,
        article_id: int,
        current_user: User = Depends(get_current_active_user)
):
    # Проверяем, есть ли уже поставщики для этого артикула
    async with aiosqlite.connect("suppliers.db") as db:
        cursor = await db.execute("SELECT code FROM articles WHERE id = ? AND user_id = ?",
                                  (article_id, current_user.id))
        article = await cursor.fetchone()

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        cursor = await db.execute("SELECT * FROM suppliers WHERE article_id = ?", (article_id,))
        existing_suppliers = await cursor.fetchall()

        if existing_suppliers:
            # Возвращаем существующих поставщиков
            suppliers = existing_suppliers
        else:
            # Выполняем поиск новых поставщиков
            suppliers_data = await search_suppliers(article[0])
            suppliers = []

            for supplier_data in suppliers_data:
                await db.execute(
                    """INSERT INTO suppliers 
                    (article_id, name, website, email, country, contact_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        article_id,
                        supplier_data.get('name'),
                        supplier_data.get('website'),
                        supplier_data.get('email'),
                        supplier_data.get('country'),
                        datetime.now().strftime("%Y-%m-%d"),
                        'new'
                    )
                )
                suppliers.append({
                    'id': cursor.lastrowid,
                    'article_id': article_id,
                    'name': supplier_data.get('name'),
                    'website': supplier_data.get('website'),
                    'email': supplier_data.get('email'),
                    'country': supplier_data.get('country'),
                    'contact_date': datetime.now().strftime("%Y-%m-%d"),
                    'status': 'new'
                })

            await db.commit()

    return templates.TemplateResponse(
        "partials/suppliers_table.html",
        {
            "request": request,
            "article_id": article_id,
            "suppliers": suppliers,
            "email_templates": await get_email_templates()
        }
    )


@app.post("/send_email/{supplier_id}", response_class=HTMLResponse)
async def send_email_to_supplier(
        request: Request,
        supplier_id: int,
        template_id: int = Form(...),
        sender_email: str = Form(...),
        current_user: User = Depends(get_current_active_user)
):
    async with aiosqlite.connect("suppliers.db") as db:
        # Получаем данные поставщика
        cursor = await db.execute("""
            SELECT s.*, a.code FROM suppliers s
            JOIN articles a ON s.article_id = a.id
            WHERE s.id = ? AND a.user_id = ?
        """, (supplier_id, current_user.id))
        supplier = await cursor.fetchone()

        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        # Получаем шаблон письма
        cursor = await db.execute("SELECT * FROM email_templates WHERE id = ?", (template_id,))
        template = await cursor.fetchone()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Отправляем письмо
        email_data = {
            "to": supplier[4],  # email поставщика
            "subject": template[2].replace("{article}", supplier[8]),  # код артикула
            "body": template[3].replace("{supplier}", supplier[2]),  # имя поставщика
            "sender": sender_email
        }

        try:
            await send_email(email_data)

            # Записываем факт отправки в базу
            await db.execute(
                """INSERT INTO sent_emails 
                (supplier_id, template_id, sender_email, sent_at, status)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    supplier_id,
                    template_id,
                    sender_email,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'sent'
                )
            )

            # Обновляем статус поставщика
            await db.execute(
                "UPDATE suppliers SET status = ? WHERE id = ?",
                ('contacted', supplier_id)
            )

            await db.commit()

            return HTMLResponse(content="Email sent successfully", status_code=200)
        except Exception as e:
            await db.execute(
                """INSERT INTO sent_emails 
                (supplier_id, template_id, sender_email, sent_at, status, error)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    supplier_id,
                    template_id,
                    sender_email,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'failed',
                    str(e)
                )
            )
            await db.commit()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics", response_class=HTMLResponse)
async def show_analytics(
        request: Request,
        current_user: User = Depends(get_current_active_user)
):
    analytics_data = await get_analytics_data(current_user.id)
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "analytics": analytics_data,
            "username": current_user.username
        }
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response