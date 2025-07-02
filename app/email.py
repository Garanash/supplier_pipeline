import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosqlite
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация SMTP (можно добавить несколько серверов)
SMTP_SERVERS = {
    'primary': {
        'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
        'port': os.getenv('SMTP_PORT', 587),
        'username': os.getenv('SMTP_USER'),
        'password': os.getenv('SMTP_PASSWORD')
    },
    'secondary': {
        'host': os.getenv('SMTP_HOST_2', 'smtp.yandex.ru'),
        'port': os.getenv('SMTP_PORT_2', 587),
        'username': os.getenv('SMTP_USER_2'),
        'password': os.getenv('SMTP_PASSWORD_2')
    }
}


async def send_email(email_data: Dict):
    """Отправка email поставщику"""
    sender_config = None

    # Выбираем конфигурацию SMTP в зависимости от отправителя
    for server_name, config in SMTP_SERVERS.items():
        if config['username'] == email_data['sender']:
            sender_config = config
            break

    if not sender_config:
        raise ValueError(f"No SMTP configuration found for sender {email_data['sender']}")

    # Создаем сообщение
    msg = MIMEMultipart()
    msg['From'] = email_data['sender']
    msg['To'] = email_data['to']
    msg['Subject'] = email_data['subject']

    # Добавляем текст письма
    msg.attach(MIMEText(email_data['body'], 'plain'))

    try:
        # Подключаемся к SMTP серверу и отправляем письмо
        with smtplib.SMTP(sender_config['host'], sender_config['port']) as server:
            server.starttls()
            server.login(sender_config['username'], sender_config['password'])
            server.send_message(msg)

        return True
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")


async def get_email_templates() -> List[Dict]:
    """Получение списка шаблонов писем из базы данных"""
    async with aiosqlite.connect("suppliers.db") as db:
        cursor = await db.execute("SELECT * FROM email_templates")
        templates = await cursor.fetchall()

        return [
            {
                'id': template[0],
                'name': template[1],
                'subject': template[2],
                'body': template[3]
            }
            for template in templates
        ]


async def get_sender_emails() -> List[str]:
    """Получение списка email для отправки"""
    return [config['username'] for config in SMTP_SERVERS.values() if config['username']]