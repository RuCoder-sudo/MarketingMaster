import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime
import threading
import pandas as pd
import io

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create the base class for models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///social_monitoring.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database
db.init_app(app)

# Import components after initializing db to avoid circular imports
from models import Project, Settings, Keyword, Mention, Log
from social_api import search_vk, search_ok, search_telegram, search_instagram
from notifications import send_notifications
from background_tasks import BackgroundSearcher
from utils import highlight_text, get_active_project, save_log

# Initialize background searcher
background_searcher = BackgroundSearcher()

# Routes
@app.route('/')
def index():
    active_project = get_active_project()
    return render_template('index.html', active_project=active_project)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    active_project = get_active_project()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save_tokens':
            # Save API tokens
            vk_token = request.form.get('vk_token')
            ok_token = request.form.get('ok_token')
            ok_public_key = request.form.get('ok_public_key')
            ok_private_key = request.form.get('ok_private_key')
            telegram_token = request.form.get('telegram_token')
            instagram_token = request.form.get('instagram_token')
            
            # Update or create settings
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings:
                settings = Settings(project_id=active_project.id)
                db.session.add(settings)
            
            # Обновляем только те токены, которые пришли в запросе
            if vk_token is not None:
                settings.vk_token = vk_token
            if ok_token is not None:
                settings.ok_token = ok_token
            if ok_public_key is not None:
                settings.ok_public_key = ok_public_key
            if ok_private_key is not None:
                settings.ok_private_key = ok_private_key
            if telegram_token is not None:
                settings.telegram_token = telegram_token
            if instagram_token is not None:
                settings.instagram_token = instagram_token
            
            db.session.commit()
            flash('API токены успешно сохранены!', 'success')
            save_log(f"API токены обновлены для проекта {active_project.name}")
            
        elif action == 'save_notifications':
            # Save notification settings
            # Update or create settings
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings:
                settings = Settings(project_id=active_project.id)
                db.session.add(settings)
            
            # Флажки для включения/выключения уведомлений
            settings.enable_email_notifications = 'enable_email_notifications' in request.form
            settings.enable_telegram_notifications = 'enable_telegram_notifications' in request.form
            
            # Email и Telegram ID для уведомлений
            settings.notification_email = request.form.get('notification_email', '')
            settings.notification_telegram_chat_id = request.form.get('notification_telegram_chat_id', '')
            
            # Интервал поиска
            search_interval = request.form.get('search_interval')
            if search_interval and search_interval.isdigit():
                settings.search_interval = int(search_interval)
            
            db.session.commit()
            flash('Настройки уведомлений успешно сохранены!', 'success')
            save_log(f"Настройки уведомлений обновлены для проекта {active_project.name}")
            
        elif action == 'add_community':
            # Add community to monitor
            social_network = request.form.get('social_network')
            community_id = request.form.get('community_id')
            
            if not community_id:
                flash('Community ID cannot be empty!', 'danger')
                return redirect(url_for('settings'))
            
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings:
                settings = Settings(project_id=active_project.id)
                db.session.add(settings)
            
            if social_network == 'vk':
                if settings.vk_communities:
                    if community_id not in settings.vk_communities.split(','):
                        settings.vk_communities = f"{settings.vk_communities},{community_id}"
                else:
                    settings.vk_communities = community_id
            elif social_network == 'ok':
                if settings.ok_communities:
                    if community_id not in settings.ok_communities.split(','):
                        settings.ok_communities = f"{settings.ok_communities},{community_id}"
                else:
                    settings.ok_communities = community_id
            elif social_network == 'telegram':
                # Remove @ from the beginning if it's there
                if community_id.startswith('@'):
                    clean_id = community_id[1:]
                else:
                    clean_id = community_id
                    
                if settings.telegram_channels:
                    if clean_id not in settings.telegram_channels.split(','):
                        settings.telegram_channels = f"{settings.telegram_channels},{clean_id}"
                else:
                    settings.telegram_channels = clean_id
            elif social_network == 'instagram':
                # Remove @ from the beginning if it's there
                if community_id.startswith('@'):
                    clean_id = community_id[1:]
                else:
                    clean_id = community_id
                    
                if settings.instagram_accounts:
                    if clean_id not in settings.instagram_accounts.split(','):
                        settings.instagram_accounts = f"{settings.instagram_accounts},{clean_id}"
                else:
                    settings.instagram_accounts = clean_id
            
            db.session.commit()
            flash(f'Community ID {community_id} added to {social_network.upper()} monitoring!', 'success')
            save_log(f"Added {social_network} community {community_id} to project {active_project.name}")
            
        elif action == 'remove_community':
            social_network = request.form.get('social_network')
            community_id = request.form.get('community_id')
            
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if settings:
                if social_network == 'vk' and settings.vk_communities:
                    communities = settings.vk_communities.split(',')
                    if community_id in communities:
                        communities.remove(community_id)
                        settings.vk_communities = ','.join(communities)
                elif social_network == 'ok' and settings.ok_communities:
                    communities = settings.ok_communities.split(',')
                    if community_id in communities:
                        communities.remove(community_id)
                        settings.ok_communities = ','.join(communities)
                elif social_network == 'telegram' and settings.telegram_channels:
                    channels = settings.telegram_channels.split(',')
                    if community_id in channels:
                        channels.remove(community_id)
                        settings.telegram_channels = ','.join(channels)
                elif social_network == 'instagram' and settings.instagram_accounts:
                    accounts = settings.instagram_accounts.split(',')
                    if community_id in accounts:
                        accounts.remove(community_id)
                        settings.instagram_accounts = ','.join(accounts)
                
                db.session.commit()
                flash(f'Community ID {community_id} removed from {social_network.upper()} monitoring!', 'success')
                save_log(f"Removed {social_network} community {community_id} from project {active_project.name}")
            
        return redirect(url_for('settings'))
    
    # Get current settings
    settings = Settings.query.filter_by(project_id=active_project.id).first()
    vk_communities = []
    ok_communities = []
    telegram_channels = []
    instagram_accounts = []
    
    if settings:
        if settings.vk_communities:
            vk_communities = settings.vk_communities.split(',')
        if settings.ok_communities:
            ok_communities = settings.ok_communities.split(',')
        if settings.telegram_channels:
            telegram_channels = settings.telegram_channels.split(',')
        if settings.instagram_accounts:
            instagram_accounts = settings.instagram_accounts.split(',')
    
    return render_template('settings.html', 
                          active_project=active_project,
                          settings=settings,
                          vk_communities=vk_communities,
                          ok_communities=ok_communities,
                          telegram_channels=telegram_channels,
                          instagram_accounts=instagram_accounts)

@app.route('/search', methods=['GET', 'POST'])
def search():
    active_project = get_active_project()
    
    # Get keywords
    keywords = Keyword.query.filter_by(project_id=active_project.id).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_keyword':
            # Add keyword
            keyword_text = request.form.get('keyword')
            color = request.form.get('color', '#ffff00')  # Default to yellow
            
            if not keyword_text:
                flash('Keyword cannot be empty!', 'danger')
                return redirect(url_for('search'))
            
            # Check if keyword already exists
            existing = Keyword.query.filter_by(
                project_id=active_project.id, 
                keyword=keyword_text
            ).first()
            
            if not existing:
                keyword = Keyword(
                    project_id=active_project.id,
                    keyword=keyword_text,
                    color=color
                )
                db.session.add(keyword)
                db.session.commit()
                flash(f'Keyword "{keyword_text}" added successfully!', 'success')
                save_log(f"Added keyword '{keyword_text}' to project {active_project.name}")
            else:
                flash(f'Keyword "{keyword_text}" already exists!', 'warning')
        
        elif action == 'remove_keyword':
            keyword_id = request.form.get('keyword_id')
            keyword = Keyword.query.get(keyword_id)
            
            if keyword and keyword.project_id == active_project.id:
                keyword_text = keyword.keyword
                db.session.delete(keyword)
                db.session.commit()
                flash(f'Keyword "{keyword_text}" removed successfully!', 'success')
                save_log(f"Removed keyword '{keyword_text}' from project {active_project.name}")
        
        elif action == 'start_search':
            # Check if we have API tokens
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings or (not settings.vk_token and not settings.ok_token):
                flash('You need to set up API tokens in Settings first!', 'danger')
                return redirect(url_for('search'))
            
            # Check if we have keywords
            if not keywords:
                flash('You need to add at least one keyword before searching!', 'danger')
                return redirect(url_for('search'))
            
            # Start background search
            background_searcher.start_search(active_project.id)
            flash('Background search started! Check the results below as they appear.', 'success')
            save_log(f"Started background search for project {active_project.name}")
            
        elif action == 'stop_search':
            # Stop background search
            background_searcher.stop_search()
            flash('Background search stopped!', 'info')
            save_log(f"Stopped background search for project {active_project.name}")
        
        elif action == 'manual_search':
            # Check if we have API tokens
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings or (not settings.vk_token and not settings.ok_token):
                flash('Необходимо настроить API токены в разделе Настройки!', 'danger')
                return redirect(url_for('search'))
            
            # Check if we have keywords
            if not keywords:
                flash('Необходимо добавить хотя бы одно ключевое слово перед поиском!', 'danger')
                return redirect(url_for('search'))
                
            # Получаем даты из формы, если они указаны
            start_date_str = request.form.get('date_from')
            end_date_str = request.form.get('date_to')
            
            start_date = None
            end_date = None
            
            # Преобразуем строки дат в объекты datetime
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    save_log(f"Поиск с начальной датой: {start_date}")
                except ValueError:
                    save_log("Неверный формат даты начала", level="ERROR")
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                    # Устанавливаем время на конец дня
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                    save_log(f"Поиск с конечной датой: {end_date}")
                except ValueError:
                    save_log("Неверный формат даты окончания", level="ERROR")
            
            # Perform manual search
            try:
                vk_count = 0
                ok_count = 0
                telegram_count = 0
                instagram_count = 0
                
                # ВКонтакте поиск
                if settings.vk_token:
                    if settings.vk_communities and settings.vk_communities.strip():
                        # VK search по конкретным сообществам
                        vk_communities = settings.vk_communities.split(',')
                        for community_id in vk_communities:
                            if community_id.strip():
                                vk_count += search_vk(active_project.id, community_id.strip(), 
                                                 [k.keyword for k in keywords], start_date, end_date)
                    else:
                        # VK search по всему ВКонтакте
                        vk_count += search_vk(active_project.id, "", [k.keyword for k in keywords], 
                                         start_date, end_date)
                
                # Одноклассники поиск
                if settings.ok_token and settings.ok_communities:
                    # OK search
                    ok_communities = settings.ok_communities.split(',')
                    for community_id in ok_communities:
                        if community_id.strip():
                            ok_count += search_ok(active_project.id, community_id.strip(), 
                                             [k.keyword for k in keywords], start_date, end_date)
                
                # Telegram поиск
                if settings.telegram_token and settings.telegram_channels:
                    # Telegram search
                    telegram_count = search_telegram(active_project.id, [k.keyword for k in keywords], 
                                               start_date, end_date)
                
                # Instagram поиск
                if settings.instagram_token and settings.instagram_accounts:
                    # Instagram search
                    instagram_count = search_instagram(active_project.id, [k.keyword for k in keywords], 
                                                 start_date, end_date)
                
                # Показываем результаты поиска
                flash_message = 'Поиск завершен! Найдено новых упоминаний: '
                flash_message += f'ВКонтакте - {vk_count}, ' if settings.vk_token else ''
                flash_message += f'Одноклассники - {ok_count}, ' if settings.ok_token and settings.ok_communities else ''
                flash_message += f'Telegram - {telegram_count}, ' if settings.telegram_token and settings.telegram_channels else ''
                flash_message += f'Instagram - {instagram_count}' if settings.instagram_token and settings.instagram_accounts else ''
                
                # Удаляем последнюю запятую, если она есть
                if flash_message.endswith(', '):
                    flash_message = flash_message[:-2]
                
                flash(flash_message, 'success')
                save_log(f"Ручной поиск завершен для проекта {active_project.name}. "
                       f"Найдено: ВК - {vk_count}, OK - {ok_count}, Telegram - {telegram_count}, Instagram - {instagram_count}")
                
                # Проверяем, нужно ли отправить уведомления
                if settings.enable_email_notifications or settings.enable_telegram_notifications:
                    total_count = vk_count + ok_count + telegram_count + instagram_count
                    if total_count > 0:
                        try:
                            # Получаем упоминания, найденные в последнюю минуту (новые упоминания из этого поиска)
                            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
                            new_mentions = Mention.query.filter(
                                Mention.project_id == active_project.id,
                                Mention.found_date >= one_minute_ago
                            ).all()
                            
                            if new_mentions:
                                save_log(f"Отправка уведомлений о {len(new_mentions)} новых упоминаниях")
                                notification_result = send_notifications(active_project.id, new_mentions)
                                
                                # Логируем результаты отправки уведомлений
                                if notification_result["email"]:
                                    save_log("Уведомление по email отправлено успешно")
                                elif settings.enable_email_notifications:
                                    save_log("Не удалось отправить уведомление по email", level="WARNING")
                                    
                                if notification_result["telegram"]:
                                    save_log("Уведомление в Telegram отправлено успешно")
                                elif settings.enable_telegram_notifications:
                                    save_log("Не удалось отправить уведомление в Telegram", level="WARNING")
                        except Exception as e:
                            save_log(f"Ошибка при отправке уведомлений: {str(e)}", level="ERROR")
                
                # Передаем в шаблон флаг, чтобы скрыть индикатор загрузки
                session['hide_loading'] = True
            except Exception as e:
                flash(f'Error during search: {str(e)}', 'danger')
                save_log(f"Error during manual search: {str(e)}", level="ERROR")
        
        elif action == 'export_csv':
            # Export mentions to CSV
            mentions = Mention.query.filter_by(project_id=active_project.id).all()
            
            if not mentions:
                flash('No data to export!', 'warning')
                return redirect(url_for('search'))
            
            # Create DataFrame
            data = []
            for mention in mentions:
                data.append({
                    'id': mention.id,
                    'social_network': mention.social_network,
                    'author_id': mention.author_id,
                    'author_name': mention.author_name,
                    'content': mention.content,
                    'post_url': mention.post_url,
                    'post_date': mention.post_date,
                    'found_date': mention.found_date
                })
            
            df = pd.DataFrame(data)
            
            # Create CSV in memory
            output = io.BytesIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"mentions_{active_project.name}_{timestamp}.csv"
            
            save_log(f"Exported data to CSV for project {active_project.name}")
            return send_file(
                output,
                mimetype='text/csv',
                download_name=filename,
                as_attachment=True
            )
        
        return redirect(url_for('search'))
    
    # Get mentions with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    mentions_query = Mention.query.filter_by(project_id=active_project.id)
    
    # Apply filters if present
    keyword_filter = request.args.get('keyword')
    if keyword_filter:
        mentions_query = mentions_query.filter(Mention.content.ilike(f'%{keyword_filter}%'))
    
    social_network_filter = request.args.get('social_network')
    if social_network_filter:
        mentions_query = mentions_query.filter_by(social_network=social_network_filter)
    
    # Order by date
    mentions_query = mentions_query.order_by(Mention.post_date.desc())
    
    # Paginate
    mentions_page = mentions_query.paginate(page=page, per_page=per_page)
    
    # Process mentions to highlight keywords
    for mention in mentions_page.items:
        mention.highlighted_content = highlight_text(mention.content, keywords)
    
    return render_template('search.html', 
                          active_project=active_project,
                          keywords=keywords,
                          mentions=mentions_page,
                          background_active=background_searcher.is_running(),
                          keyword_filter=keyword_filter,
                          social_network_filter=social_network_filter)

@app.route('/logs')
def logs():
    active_project = get_active_project()
    
    # Get logs with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs_query = Log.query.filter_by(project_id=active_project.id).order_by(Log.timestamp.desc())
    logs_page = logs_query.paginate(page=page, per_page=per_page)
    
    return render_template('logs.html', 
                          active_project=active_project,
                          logs=logs_page)

@app.route('/logs/clear', methods=['POST'])
def clear_logs():
    active_project = get_active_project()
    
    # Delete all logs for the current project
    Log.query.filter_by(project_id=active_project.id).delete()
    db.session.commit()
    
    flash('Logs cleared successfully!', 'success')
    return redirect(url_for('logs'))

@app.route('/logs/export', methods=['POST'])
def export_logs():
    active_project = get_active_project()
    
    # Get all logs for the current project
    logs = Log.query.filter_by(project_id=active_project.id).order_by(Log.timestamp.desc()).all()
    
    if not logs:
        flash('No logs to export!', 'warning')
        return redirect(url_for('logs'))
    
    # Create DataFrame
    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'timestamp': log.timestamp,
            'level': log.level,
            'message': log.message
        })
    
    df = pd.DataFrame(data)
    
    # Create CSV in memory
    output = io.BytesIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"logs_{active_project.name}_{timestamp}.csv"
    
    return send_file(
        output,
        mimetype='text/csv',
        download_name=filename,
        as_attachment=True
    )

@app.route('/export/pdf')
def export_pdf():
    """Экспортировать данные о мониторинге в PDF отчет"""
    from datetime import timedelta
    import weasyprint
    
    active_project = get_active_project()
    
    # Получаем параметры фильтрации из запроса
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    social_network = request.args.get('social_network')
    
    # Преобразуем строки дат в объекты datetime, если они указаны
    start_date = None
    end_date = None
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            pass
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d')
            # Устанавливаем время на конец дня
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    
    # Базовый запрос для получения упоминаний
    query = Mention.query.filter_by(project_id=active_project.id)
    
    # Применяем фильтры
    if start_date:
        query = query.filter(Mention.post_date >= start_date)
    
    if end_date:
        query = query.filter(Mention.post_date <= end_date)
    
    if social_network:
        query = query.filter(Mention.social_network == social_network)
    
    # Получаем все упоминания с применёнными фильтрами и сортируем по дате (новые - вверху)
    mentions = query.order_by(Mention.post_date.desc()).all()
    
    # Считаем статистику
    total_mentions = len(mentions)
    positive_mentions = len([m for m in mentions if m.sentiment == 'positive'])
    negative_mentions = len([m for m in mentions if m.sentiment == 'negative'])
    neutral_mentions = total_mentions - positive_mentions - negative_mentions
    
    # Статистика по социальным сетям
    networks_data = {
        'vk': len([m for m in mentions if m.social_network == 'vk']),
        'ok': len([m for m in mentions if m.social_network == 'ok']),
        'telegram': len([m for m in mentions if m.social_network == 'telegram']),
        'instagram': len([m for m in mentions if m.social_network == 'instagram'])
    }
    
    # Подсвечиваем ключевые слова в контенте
    keywords = Keyword.query.filter_by(project_id=active_project.id).all()
    for mention in mentions:
        mention.content = highlight_text(mention.content, keywords)
    
    # Статистика по ключевым словам
    keywords_stats = {}
    
    for keyword in keywords:
        count = 0
        for mention in mentions:
            if keyword.keyword.lower() in mention.content.lower():
                count += 1
        keywords_stats[keyword.keyword] = count
    
    # Сортируем ключевые слова по количеству упоминаний (в порядке убывания)
    sorted_keywords = sorted(keywords_stats.items(), key=lambda x: x[1], reverse=True)
    
    # Берем только топ-10 ключевых слов
    top_keywords = sorted_keywords[:10]
    keywords_labels = [item[0] for item in top_keywords]
    keywords_values = [item[1] for item in top_keywords]
    
    # Формируем HTML отчёт
    html = render_template('export_pdf.html',
                          current_date=datetime.now().strftime('%d.%m.%Y %H:%M'),
                          project=active_project,
                          date_from=start_date.strftime('%d.%m.%Y') if start_date else None,
                          date_to=end_date.strftime('%d.%m.%Y') if end_date else None,
                          total_mentions=total_mentions,
                          positive_mentions=positive_mentions,
                          negative_mentions=negative_mentions,
                          neutral_mentions=neutral_mentions,
                          networks_data=networks_data,
                          mentions=mentions,
                          keywords_labels=keywords_labels,
                          keywords_values=keywords_values,
                          zip=zip)
    
    # Генерируем PDF из HTML
    pdf = weasyprint.HTML(string=html).write_pdf()
    
    # Создаем BytesIO объект для отправки файла
    result = io.BytesIO(pdf)
    result.seek(0)
    
    # Формируем имя файла
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{active_project.name}_{timestamp}.pdf"
    
    # Отправляем PDF файл
    return send_file(
        result,
        mimetype='application/pdf',
        download_name=filename,
        as_attachment=True
    )

@app.route('/analytics')
def analytics():
    active_project = get_active_project()
    
    # Получаем параметры фильтрации из запроса
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    social_network = request.args.get('social_network')
    
    # Преобразуем строки дат в объекты datetime, если они указаны
    start_date = None
    end_date = None
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            flash('Некорректный формат начальной даты!', 'warning')
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d')
            # Устанавливаем время на конец дня
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            flash('Некорректный формат конечной даты!', 'warning')
    
    # Базовый запрос для получения упоминаний
    query = Mention.query.filter_by(project_id=active_project.id)
    
    # Применяем фильтры
    if start_date:
        query = query.filter(Mention.post_date >= start_date)
    
    if end_date:
        query = query.filter(Mention.post_date <= end_date)
    
    if social_network:
        query = query.filter(Mention.social_network == social_network)
    
    # Получаем все упоминания с применёнными фильтрами
    mentions = query.all()
    
    # Считаем статистику
    total_mentions = len(mentions)
    positive_mentions = len([m for m in mentions if m.sentiment == 'positive'])
    negative_mentions = len([m for m in mentions if m.sentiment == 'negative'])
    neutral_mentions = total_mentions - positive_mentions - negative_mentions
    
    # Статистика по социальным сетям
    networks_data = {
        'vk': len([m for m in mentions if m.social_network == 'vk']),
        'ok': len([m for m in mentions if m.social_network == 'ok']),
        'telegram': len([m for m in mentions if m.social_network == 'telegram']),
        'instagram': len([m for m in mentions if m.social_network == 'instagram'])
    }
    
    # Временная динамика (по дням)
    if mentions:
        # Сортируем упоминания по дате
        sorted_mentions = sorted(mentions, key=lambda m: m.post_date if m.post_date else m.found_date)
        
        # Группируем по датам
        from collections import defaultdict
        timeline_data = defaultdict(int)
        
        for mention in sorted_mentions:
            date = (mention.post_date if mention.post_date else mention.found_date).strftime('%Y-%m-%d')
            timeline_data[date] += 1
        
        timeline_labels = list(timeline_data.keys())
        timeline_values = list(timeline_data.values())
    else:
        timeline_labels = []
        timeline_values = []
    
    # Статистика по ключевым словам
    keywords = Keyword.query.filter_by(project_id=active_project.id).all()
    keywords_stats = {}
    
    for keyword in keywords:
        count = 0
        for mention in mentions:
            if keyword.keyword.lower() in mention.content.lower():
                count += 1
        keywords_stats[keyword.keyword] = count
    
    # Сортируем ключевые слова по количеству упоминаний (в порядке убывания)
    sorted_keywords = sorted(keywords_stats.items(), key=lambda x: x[1], reverse=True)
    
    # Берем только топ-10 ключевых слов
    top_keywords = sorted_keywords[:10]
    keywords_labels = [item[0] for item in top_keywords]
    keywords_values = [item[1] for item in top_keywords]
    
    return render_template('analytics.html', 
                          active_project=active_project,
                          total_mentions=total_mentions,
                          positive_mentions=positive_mentions,
                          negative_mentions=negative_mentions,
                          neutral_mentions=neutral_mentions,
                          networks_data=networks_data,
                          timeline_labels=timeline_labels,
                          timeline_values=timeline_values,
                          keywords_labels=keywords_labels,
                          keywords_values=keywords_values)

@app.route('/extra')
def extra():
    active_project = get_active_project()
    return render_template('extra.html', active_project=active_project)

@app.route('/projects', methods=['GET', 'POST'])
def project_management():
    active_project = get_active_project()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_project':
            project_name = request.form.get('project_name')
            
            if not project_name:
                flash('Project name cannot be empty!', 'danger')
                return redirect(url_for('project_management'))
            
            # Check if a project with this name already exists
            existing = Project.query.filter_by(name=project_name).first()
            if existing:
                flash(f'Project "{project_name}" already exists!', 'warning')
                return redirect(url_for('project_management'))
            
            # Check if we've reached the limit (5 projects)
            projects_count = Project.query.count()
            if projects_count >= 5:
                flash('Maximum number of projects (5) reached. Please delete a project first.', 'danger')
                return redirect(url_for('project_management'))
            
            # Create new project
            project = Project(name=project_name)
            db.session.add(project)
            db.session.commit()
            
            flash(f'Project "{project_name}" created successfully!', 'success')
            save_log(f"Created project {project_name}")
            
        elif action == 'delete_project':
            project_id = request.form.get('project_id')
            project = Project.query.get(project_id)
            
            if project:
                project_name = project.name
                
                # Don't delete if it's the only project
                if Project.query.count() <= 1:
                    flash('Cannot delete the only project!', 'danger')
                    return redirect(url_for('project_management'))
                
                # Delete related data
                Settings.query.filter_by(project_id=project.id).delete()
                Keyword.query.filter_by(project_id=project.id).delete()
                Mention.query.filter_by(project_id=project.id).delete()
                Log.query.filter_by(project_id=project.id).delete()
                
                # Delete the project
                db.session.delete(project)
                db.session.commit()
                
                flash(f'Project "{project_name}" deleted successfully!', 'success')
                
                # If we deleted the active project, select another one
                if active_project.id == int(project_id):
                    new_active = Project.query.first()
                    if new_active:
                        return redirect(url_for('set_active_project', project_id=new_active.id))
            
        elif action == 'rename_project':
            project_id = request.form.get('project_id')
            new_name = request.form.get('new_name')
            
            if not new_name:
                flash('Project name cannot be empty!', 'danger')
                return redirect(url_for('project_management'))
            
            project = Project.query.get(project_id)
            if project:
                old_name = project.name
                project.name = new_name
                db.session.commit()
                
                flash(f'Project renamed from "{old_name}" to "{new_name}" successfully!', 'success')
                save_log(f"Renamed project from {old_name} to {new_name}")
        
        return redirect(url_for('project_management'))
    
    # Get all projects
    projects = Project.query.all()
    
    return render_template('project_management.html', 
                          active_project=active_project,
                          projects=projects)

@app.route('/set_active_project/<int:project_id>')
def set_active_project(project_id):
    project = Project.query.get(project_id)
    
    if project:
        # Set as active in session
        app.config['ACTIVE_PROJECT_ID'] = project.id
        flash(f'Switched to project: {project.name}', 'success')
    
    return redirect(request.referrer or url_for('index'))

# Initialize the database with app context
with app.app_context():
    # Create all tables
    db.create_all()
    
    # Create a default project if none exists
    if Project.query.count() == 0:
        default_project = Project(name="Default Project")
        db.session.add(default_project)
        db.session.commit()
        app.config['ACTIVE_PROJECT_ID'] = default_project.id
