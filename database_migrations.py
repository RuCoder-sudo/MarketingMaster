import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Создаем временное приложение Flask для миграции
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def run_migrations():
    """Запускает миграции базы данных для добавления новых полей"""
    with app.app_context():
        try:
            logger.info("Начинаем миграцию базы данных...")
            
            # Проверяем существующие таблицы
            tables = db.session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
            table_names = [table[0] for table in tables]
            logger.info(f"Существующие таблицы: {table_names}")
            
            # Миграции для таблицы Settings
            logger.info("Добавляем столбцы в таблицу Settings...")
            
            # Проверяем и добавляем новые столбцы
            columns = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'settings'"
            )).fetchall()
            
            existing_columns = [col[0] for col in columns]
            logger.info(f"Существующие столбцы в settings: {existing_columns}")
            
            # Добавляем telegram_token если его нет
            if 'telegram_token' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN telegram_token VARCHAR(255)"))
                logger.info("Добавлен столбец telegram_token")
            
            # Добавляем instagram_token если его нет
            if 'instagram_token' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN instagram_token VARCHAR(255)"))
                logger.info("Добавлен столбец instagram_token")
            
            # Добавляем telegram_channels если его нет
            if 'telegram_channels' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN telegram_channels TEXT"))
                logger.info("Добавлен столбец telegram_channels")
            
            # Добавляем instagram_accounts если его нет
            if 'instagram_accounts' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN instagram_accounts TEXT"))
                logger.info("Добавлен столбец instagram_accounts")
            
            # Добавляем enable_email_notifications если его нет
            if 'enable_email_notifications' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN enable_email_notifications BOOLEAN DEFAULT FALSE"))
                logger.info("Добавлен столбец enable_email_notifications")
            
            # Добавляем notification_email если его нет
            if 'notification_email' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN notification_email VARCHAR(100)"))
                logger.info("Добавлен столбец notification_email")
            
            # Добавляем enable_telegram_notifications если его нет
            if 'enable_telegram_notifications' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN enable_telegram_notifications BOOLEAN DEFAULT FALSE"))
                logger.info("Добавлен столбец enable_telegram_notifications")
            
            # Добавляем notification_telegram_chat_id если его нет
            if 'notification_telegram_chat_id' not in existing_columns:
                db.session.execute(text("ALTER TABLE settings ADD COLUMN notification_telegram_chat_id VARCHAR(100)"))
                logger.info("Добавлен столбец notification_telegram_chat_id")
                
            # Миграции для таблицы Mention
            logger.info("Проверяем и добавляем столбцы в таблицу Mention...")
            
            # Проверяем существующие столбцы
            columns = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'mention'"
            )).fetchall()
            
            existing_columns = [col[0] for col in columns]
            logger.info(f"Существующие столбцы в mention: {existing_columns}")
            
            # Добавляем channel_name если его нет
            if 'channel_name' not in existing_columns:
                db.session.execute(text("ALTER TABLE mention ADD COLUMN channel_name VARCHAR(100)"))
                logger.info("Добавлен столбец channel_name")
            
            # Добавляем chat_id если его нет
            if 'chat_id' not in existing_columns:
                db.session.execute(text("ALTER TABLE mention ADD COLUMN chat_id VARCHAR(50)"))
                logger.info("Добавлен столбец chat_id")
            
            # Добавляем message_id если его нет
            if 'message_id' not in existing_columns:
                db.session.execute(text("ALTER TABLE mention ADD COLUMN message_id VARCHAR(50)"))
                logger.info("Добавлен столбец message_id")
            
            # Добавляем sentiment если его нет
            if 'sentiment' not in existing_columns:
                db.session.execute(text("ALTER TABLE mention ADD COLUMN sentiment VARCHAR(10)"))
                logger.info("Добавлен столбец sentiment")
            
            # Подтверждаем все изменения
            db.session.commit()
            logger.info("Миграция успешно завершена!")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка при миграции: {str(e)}")
            return False

if __name__ == "__main__":
    run_migrations()