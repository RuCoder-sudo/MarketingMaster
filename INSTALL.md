# Инструкция по установке MarketingMaster на сервер

## Оглавление
1. [Требования](#требования)
2. [Подключение к серверу через MobaXterm](#подключение-к-серверу-через-mobaxterm)
3. [Подготовка сервера](#подготовка-сервера)
4. [Клонирование репозитория](#клонирование-репозитория)
5. [Настройка окружения Python](#настройка-окружения-python)
6. [Настройка PostgreSQL](#настройка-postgresql)
7. [Настройка переменных окружения](#настройка-переменных-окружения)
8. [Запуск приложения](#запуск-приложения)
9. [Настройка Nginx](#настройка-nginx)
10. [Настройка Gunicorn как службы](#настройка-gunicorn-как-службы)
11. [Настройка SSL с Let's Encrypt](#настройка-ssl-с-lets-encrypt)
12. [Проверка работоспособности](#проверка-работоспособности)
13. [Решение возможных проблем](#решение-возможных-проблем)

## Требования
- Сервер под управлением Debian/Ubuntu/CentOS
- Доступ по SSH к серверу (логин и пароль)
- Доменное имя, настроенное на IP-адрес сервера

## Подключение к серверу через MobaXterm

1. Откройте MobaXterm
2. Нажмите на кнопку "Session" в верхнем левом углу
3. Выберите "SSH"
4. Введите данные сервера:
   - Remote host: f418b3c5b5c3.vps.myjino.ru (или IP-адрес вашего сервера)
   - Specify username: root
   - Port: 22 (стандартный порт SSH)
5. Нажмите "OK"
6. Введите пароль при запросе

## Подготовка сервера

После подключения к серверу выполните следующие команды для обновления системы и установки необходимых пакетов:

```bash
# Обновление системы
apt update
apt upgrade -y

# Установка необходимых пакетов
apt install -y python3 python3-pip python3-venv git nginx postgresql postgresql-contrib python3-dev libpq-dev
```

## Клонирование репозитория

Создайте директорию для проекта и клонируйте репозиторий:

```bash
# Создание директории
mkdir -p /var/www
cd /var/www

# Клонирование репозитория
git clone https://github.com/RuCoder-sudo/MarketingMaster.git
cd MarketingMaster
```

## Настройка окружения Python

Создайте виртуальное окружение Python и установите зависимости:

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация окружения
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install email-validator flask flask-sqlalchemy gunicorn pandas psycopg2-binary requests sendgrid sqlalchemy trafilatura werkzeug
```

## Настройка PostgreSQL

Настройте базу данных PostgreSQL:

```bash
# Вход в PostgreSQL
sudo -u postgres psql

# Создание пользователя и базы данных
CREATE USER marketingmaster WITH PASSWORD 'ваш_надежный_пароль';
CREATE DATABASE marketingmaster OWNER marketingmaster;
ALTER USER marketingmaster WITH SUPERUSER;
\q

# Проверка подключения к базе данных
psql -U marketingmaster -d marketingmaster -h localhost
# Введите пароль, который вы установили выше
```

## Настройка переменных окружения

Создайте файл с переменными окружения:

```bash
# Создание файла .env
cat > /var/www/MarketingMaster/.env << EOL
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=вставьте_здесь_надежный_секретный_ключ
DATABASE_URL=postgresql://marketingmaster:ваш_надежный_пароль@localhost/marketingmaster
EOL

# Установка прав доступа
chmod 600 /var/www/MarketingMaster/.env
```

## Запуск приложения

Запустите приложение вручную, чтобы проверить, что все работает:

```bash
# Активация виртуального окружения, если оно еще не активировано
cd /var/www/MarketingMaster
source venv/bin/activate

# Запуск Flask для проверки
export $(cat .env | xargs)
python main.py
```

Приложение должно запуститься на порту 5000. Нажмите Ctrl+C для остановки после проверки.

## Настройка Nginx

Настройте Nginx для работы с вашим приложением:

```bash
# Создание конфигурационного файла Nginx
cat > /etc/nginx/sites-available/marketingmaster.conf << EOL
server {
    listen 80;
    server_name marketingmaster.space www.marketingmaster.space;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias /var/www/MarketingMaster/static;
        expires 30d;
    }
}
EOL

# Активация конфигурации
ln -s /etc/nginx/sites-available/marketingmaster.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Удаление конфигурации по умолчанию

# Проверка конфигурации Nginx
nginx -t

# Перезапуск Nginx
systemctl restart nginx
```

## Настройка Gunicorn как службы

Настройте Gunicorn как системную службу для запуска приложения:

```bash
# Создание файла службы systemd
cat > /etc/systemd/system/marketingmaster.service << EOL
[Unit]
Description=MarketingMaster Gunicorn Service
After=network.target postgresql.service

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/MarketingMaster
Environment="PATH=/var/www/MarketingMaster/venv/bin"
EnvironmentFile=/var/www/MarketingMaster/.env
ExecStart=/var/www/MarketingMaster/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --reuse-port --reload main:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

# Включение и запуск службы
systemctl daemon-reload
systemctl enable marketingmaster.service
systemctl start marketingmaster.service

# Проверка статуса службы
systemctl status marketingmaster.service
```

## Настройка SSL с Let's Encrypt

Установите и настройте SSL-сертификат с помощью Let's Encrypt:

```bash
# Установка Certbot
apt install -y certbot python3-certbot-nginx

# Получение сертификата
certbot --nginx -d marketingmaster.space -d www.marketingmaster.space

# Проверка автоматического обновления
certbot renew --dry-run
```

## Проверка работоспособности

Проверьте, что ваше приложение доступно через веб-браузер:

1. Откройте браузер
2. Введите в адресной строке: https://marketingmaster.space
3. Убедитесь, что сайт загружается и работает корректно

## Решение возможных проблем

### Приложение не запускается

Проверьте логи:

```bash
journalctl -u marketingmaster.service -f
```

### Проблемы с базой данных

Проверьте подключение к базе данных:

```bash
# Активация окружения
cd /var/www/MarketingMaster
source venv/bin/activate

# Проверка подключения
python -c "import psycopg2; conn = psycopg2.connect('postgresql://marketingmaster:ваш_надежный_пароль@localhost/marketingmaster'); print('Подключение успешно!')"
```

### Проблемы с Nginx

Проверьте логи Nginx:

```bash
cat /var/log/nginx/error.log
```

### Проверка портов

Убедитесь, что Gunicorn слушает порт 5000:

```bash
netstat -tulpn | grep 5000
```

### Проблемы с правами доступа

Исправьте права доступа к файлам:

```bash
# Установка правильных прав
chown -R root:www-data /var/www/MarketingMaster
chmod -R 755 /var/www/MarketingMaster
```

## Дополнительные рекомендации

### Автоматическое обновление из репозитория

Создайте скрипт для автоматического обновления приложения из репозитория:

```bash
cat > /var/www/update_marketingmaster.sh << EOL
#!/bin/bash
cd /var/www/MarketingMaster
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart marketingmaster.service
EOL

chmod +x /var/www/update_marketingmaster.sh
```

### Настройка резервного копирования базы данных

Настройте автоматическое резервное копирование базы данных:

```bash
cat > /var/www/backup_database.sh << EOL
#!/bin/bash
BACKUP_DIR="/var/www/backups"
TIMESTAMP=\$(date +"%Y%m%d_%H%M%S")
mkdir -p \$BACKUP_DIR
pg_dump -U marketingmaster -d marketingmaster -h localhost > "\$BACKUP_DIR/marketingmaster_\$TIMESTAMP.sql"
EOL

chmod +x /var/www/backup_database.sh

# Добавление в cron для ежедневного выполнения
(crontab -l 2>/dev/null; echo "0 2 * * * /var/www/backup_database.sh") | crontab -
```

### Мониторинг приложения

Рассмотрите установку системы мониторинга, например, Prometheus + Grafana, для отслеживания работы приложения.

---

Эта инструкция содержит все необходимые шаги для установки и настройки MarketingMaster на вашем сервере. В случае возникновения проблем или вопросов, обратитесь к документации или обратитесь за поддержкой.