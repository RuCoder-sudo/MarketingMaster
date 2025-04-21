Создание инструкции по запуску проекта
# Мониторинг упоминаний в соцсетях

## Описание
Этот проект позволяет отслеживать упоминания в ВКонтакте и Одноклассниках.

## Требования
- Python 3.x
- PostgreSQL
- Nginx

## Установка

1. **Клонирование репозитория**

   ```bash
   git clone https://github.com/RuCoder-sudo/social_monitoring.git
   cd social_monitoring
Создание и активация виртуального окружения

python3 -m venv venv
source venv/bin/activate
Установка зависимостей

pip install -r requirements.txt
Настройка базы данных

Создайте пользователя и базу данных в PostgreSQL:
sudo -u postgres psql
CREATE USER social_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE social_monitoring OWNER social_user;
\q
Создание конфигурационного файла

Создайте файл .env в корне проекта с содержимым:

DATABASE_URL=postgresql://social_user:your_secure_password@localhost/social_monitoring
SESSION_SECRET=`openssl rand -hex 32`
Настройка и запуск приложения

**Запустите приложение с помощью Gunicorn:
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
Настройте Nginx как обратный прокси (инструкции выше).
