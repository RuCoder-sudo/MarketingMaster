# Полное руководство по сбросу и настройке сервера

Это руководство поможет вам полностью сбросить ваш сервер к исходному состоянию, а затем правильно настроить и запустить приложение мониторинга социальных сетей.

## Часть 1: Полный сброс сервера

Следующие команды полностью очистят ваш сервер, удалив все предыдущие установки и данные.

### 1. Остановка и удаление всех запущенных служб

```bash
# Остановка сервисов
systemctl stop social_monitoring
systemctl stop nginx
systemctl stop postgresql

# Отключение сервисов от автозапуска
systemctl disable social_monitoring
systemctl disable nginx
systemctl disable postgresql
```

### 2. Удаление всех установленных пакетов и зависимостей

```bash
# Обновление списка пакетов
apt update

# Удаление всех пакетов, связанных с проектом
apt purge -y nginx python3-pip python3-venv postgresql postgresql-contrib
apt purge -y python3-dev build-essential libssl-dev libffi-dev libpq-dev

# Удаление зависимостей, которые больше не нужны
apt autoremove -y

# Очистка кэша apt
apt clean
```

### 3. Удаление всех файлов проекта и баз данных

```bash
# Удаление файлов проекта
rm -rf /var/www/social_monitoring
rm -rf /etc/nginx/sites-available/social_monitoring
rm -rf /etc/nginx/sites-enabled/social_monitoring
rm -rf /etc/systemd/system/social_monitoring.service

# Удаление базы данных PostgreSQL
# Сначала переключиться на пользователя postgres
su - postgres
# Удалить базу данных и пользователя
psql -c "DROP DATABASE IF EXISTS social_monitoring;"
psql -c "DROP USER IF EXISTS social_user;"
# Выйти из пользователя postgres
exit
```

### 4. Перезагрузка сервера

```bash
# Перезагрузка системы
reboot
```

## Часть 2: Установка и настройка нового сервера

После перезагрузки сервера следуйте этим инструкциям для установки необходимых компонентов и запуска проекта.

### 1. Установка необходимых пакетов

```bash
# Обновление списка пакетов
apt update
apt upgrade -y

# Установка необходимых пакетов
apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib
apt install -y python3-dev build-essential libssl-dev libffi-dev libpq-dev git
```

### 2. Настройка базы данных PostgreSQL

```bash
# Запуск сервиса PostgreSQL
systemctl start postgresql
systemctl enable postgresql

# Переключение на пользователя postgres для создания БД
su - postgres

# Создание пользователя базы данных
psql -c "CREATE USER social_user WITH PASSWORD 'your_secure_password';"

# Создание базы данных
psql -c "CREATE DATABASE social_monitoring OWNER social_user;"

# Выйти из пользователя postgres
exit
```

### 3. Настройка проекта

```bash
# Создание директории проекта
mkdir -p /var/www/social_monitoring

# Загрузка файлов проекта из вашего источника
# Например, из ZIP-архива или через git clone
# git clone https://your_repository.git /var/www/social_monitoring
# или разархивировать ваш архив с проектом:
unzip /path/to/your/project.zip -d /var/www/social_monitoring

# Изменение владельца файлов
chown -R www-data:www-data /var/www/social_monitoring

# Переход в директорию проекта
cd /var/www/social_monitoring
```

### 4. Настройка виртуального окружения Python и установка зависимостей

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
# Если файла requirements.txt нет, установите необходимые пакеты:
pip install flask flask-sqlalchemy psycopg2-binary gunicorn requests pandas openpyxl
```

### 5. Конфигурация переменных окружения

Создайте файл конфигурации окружения:

```bash
# Создание файла .env
cat > /var/www/social_monitoring/.env << EOF
DATABASE_URL=postgresql://social_user:your_secure_password@localhost/social_monitoring
SESSION_SECRET=your_very_secure_random_secret_key
EOF
```

### 6. Настройка Systemd сервиса для автозапуска приложения

```bash
# Создание файла сервиса
cat > /etc/systemd/system/social_monitoring.service << EOF
[Unit]
Description=Social Monitoring App
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/social_monitoring
Environment="PATH=/var/www/social_monitoring/venv/bin"
EnvironmentFile=/var/www/social_monitoring/.env
ExecStart=/var/www/social_monitoring/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 --access-logfile /var/log/social_monitoring/access.log --error-logfile /var/log/social_monitoring/error.log main:app

[Install]
WantedBy=multi-user.target
EOF

# Создание директории для логов
mkdir -p /var/log/social_monitoring
chown -R www-data:www-data /var/log/social_monitoring

# Разрешение запуска сервиса и его автозапуск
systemctl daemon-reload
systemctl enable social_monitoring
systemctl start social_monitoring
```

### 7. Настройка Nginx как обратного прокси

```bash
# Создание конфигурации сайта
cat > /etc/nginx/sites-available/social_monitoring << EOF
server {
    listen 80;
    server_name your_domain.com;  # Замените на ваш домен или IP-адрес сервера

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Дополнительные настройки безопасности
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";
}
EOF

# Активация сайта
ln -s /etc/nginx/sites-available/social_monitoring /etc/nginx/sites-enabled/

# Проверка конфигурации Nginx
nginx -t

# Запуск и автозапуск Nginx
systemctl restart nginx
systemctl enable nginx
```

### 8. Настройка брандмауэра (опционально)

```bash
# Установка UFW (если не установлен)
apt install -y ufw

# Настройка правил брандмауэра
ufw allow ssh
ufw allow http
ufw allow https

# Включение брандмауэра
ufw enable
```

### 9. Проверка работоспособности приложения

```bash
# Проверка статуса сервиса
systemctl status social_monitoring

# Просмотр логов приложения
journalctl -u social_monitoring -f
```

## Часть 3: Обслуживание и обновление приложения

### Обновление приложения

Когда вам нужно обновить файлы приложения:

```bash
# Остановка сервиса
systemctl stop social_monitoring

# Сделайте резервную копию текущих файлов
cp -r /var/www/social_monitoring /var/www/social_monitoring_backup_$(date +%Y%m%d)

# Обновите файлы (загрузите новые версии)
# ... команды для загрузки новых файлов ...

# Обновление зависимостей (если необходимо)
cd /var/www/social_monitoring
source venv/bin/activate
pip install -r requirements.txt

# Запуск сервиса
systemctl start social_monitoring
```

### Резервное копирование базы данных

Регулярно делайте резервные копии базы данных:

```bash
# Создание резервной копии базы данных
pg_dump -U postgres social_monitoring > /backup/social_monitoring_$(date +%Y%m%d).sql

# Восстановление базы из резервной копии (при необходимости)
psql -U postgres -d social_monitoring < /backup/social_monitoring_backup.sql
```

## Дополнительные рекомендации

1. **Безопасность**: Регулярно обновляйте систему и пакеты с помощью `apt update && apt upgrade`.
2. **Мониторинг**: Настройте мониторинг сервера с использованием инструментов, таких как Prometheus, Grafana или более простые решения, как Monit.
3. **Резервное копирование**: Настройте регулярное резервное копирование всего проекта и базы данных.
4. **SSL**: Для продакшн-версии настройте HTTPS с помощью Let's Encrypt.

```bash
# Установка Certbot для Let's Encrypt
apt install -y certbot python3-certbot-nginx

# Получение SSL-сертификата
certbot --nginx -d your_domain.com
```

## Устранение неполадок

### Проблема с подключением к базе данных
1. Проверьте правильность конфигурации в `.env` файле
2. Убедитесь, что PostgreSQL запущен: `systemctl status postgresql`
3. Проверьте доступность пользователя базы данных:
   ```
   su - postgres
   psql -c "\du"
   ```

### Приложение не запускается
1. Проверьте логи: `journalctl -u social_monitoring -f`
2. Убедитесь, что все зависимости установлены: `pip list`
3. Проверьте права доступа к файлам проекта