import os
import aiosqlite
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./suppliers.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


async def init_db():
    async with aiosqlite.connect("suppliers.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                website TEXT NOT NULL,
                email TEXT,
                country TEXT,
                contact_date TEXT,
                status TEXT DEFAULT 'new',
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                sender_email TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
                FOREIGN KEY (template_id) REFERENCES email_templates (id)
            )
        """)

        # Добавляем тестовые шаблоны писем, если их нет
        await db.execute("""
            INSERT OR IGNORE INTO email_templates (name, subject, price_request) VALUES 
            ('Price Request', 'Request for quotation - {article}', 'Dear {supplier},\\n\\nWe are interested in your product {article}. Please provide your best offer.\\n\\nBest regards,\\nPurchasing Department'),
            ('Information Request', 'Information request - {article}', 'Dear {supplier},\\n\\nWe would like to get more information about your product {article}.\\n\\nBest regards,\\nPurchasing Department'),
            ('Offer Submission', 'Offer submission - {article}', 'Dear {supplier},\\n\\nThank you for your offer. We will review it and get back to you.\\n\\nBest regards,\\nPurchasing Department')
        """)

        await db.commit()


async def get_db():
    async with aiosqlite.connect("suppliers.db") as db:
        yield db