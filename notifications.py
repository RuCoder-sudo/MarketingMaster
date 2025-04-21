import os
import requests
from datetime import datetime
from flask import current_app
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from utils import save_log
from models import Settings, Project, Mention

def send_email_notification(project_id, mentions):
    """
    Send email notification about new mentions
    
    Args:
        project_id (int): Project ID
        mentions (list): List of Mention objects
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    settings = Settings.query.filter_by(project_id=project_id).first()
    
    if not settings or not settings.enable_email_notifications or not settings.notification_email:
        return False
    
    try:
        # Check if we have SendGrid API key
        sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_api_key:
            save_log("SENDGRID_API_KEY environment variable not set", level="ERROR")
            return False
        
        # Get project details
        project = Project.query.get(project_id)
        if not project:
            save_log(f"Project {project_id} not found", level="ERROR")
            return False
        
        # Create email content
        subject = f"Новые упоминания в проекте '{project.name}'"
        
        html_content = f"""
        <h2>Обнаружены новые упоминания в проекте '{project.name}'</h2>
        <p>Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        <h3>Новые упоминания:</h3>
        <ul>
        """
        
        # Add mentions to the email
        for mention in mentions:
            network_name = {
                'vk': 'ВКонтакте',
                'ok': 'Одноклассники',
                'telegram': 'Telegram',
                'instagram': 'Instagram'
            }.get(mention.social_network, mention.social_network)
            
            html_content += f"""
            <li>
                <strong>{network_name}</strong>: 
                <a href="{mention.post_url}" target="_blank">Просмотреть пост</a><br>
                <em>{mention.post_date.strftime('%d.%m.%Y %H:%M') if mention.post_date else 'Дата не указана'}</em><br>
                Текст: {mention.content[:150]}{'...' if len(mention.content) > 150 else ''}
            </li>
            """
        
        html_content += """
        </ul>
        <p>С уважением, система мониторинга социальных сетей.</p>
        """
        
        # Create SendGrid message
        message = Mail(
            from_email=Email("noreply@socialmonitoring.ru"),
            to_emails=To(settings.notification_email),
            subject=subject
        )
        message.content = Content("text/html", html_content)
        
        # Send email
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code >= 200 and response.status_code < 300:
            save_log(f"Email notification sent successfully to {settings.notification_email}")
            return True
        else:
            save_log(f"Failed to send email notification: {response.status_code} {response.body}", level="ERROR")
            return False
    
    except Exception as e:
        save_log(f"Error sending email notification: {str(e)}", level="ERROR")
        return False

def send_telegram_notification(project_id, mentions):
    """
    Send Telegram notification about new mentions
    
    Args:
        project_id (int): Project ID
        mentions (list): List of Mention objects
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    settings = Settings.query.filter_by(project_id=project_id).first()
    
    if (not settings or not settings.enable_telegram_notifications or 
        not settings.notification_telegram_chat_id or not settings.telegram_token):
        return False
    
    try:
        # Get project details
        project = Project.query.get(project_id)
        if not project:
            save_log(f"Project {project_id} not found", level="ERROR")
            return False
        
        # Create message content
        message = f"🔔 *Новые упоминания в проекте '{project.name}'*\n"
        message += f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        
        # Add mentions to the message
        for i, mention in enumerate(mentions[:5], 1):  # Limit to first 5 mentions
            network_name = {
                'vk': 'ВКонтакте',
                'ok': 'Одноклассники',
                'telegram': 'Telegram',
                'instagram': 'Instagram'
            }.get(mention.social_network, mention.social_network)
            
            message += f"{i}. *{network_name}*: "
            message += f"[Просмотреть пост]({mention.post_url})\n"
            message += f"Дата: {mention.post_date.strftime('%d.%m.%Y %H:%M') if mention.post_date else 'Не указана'}\n"
            
            # Truncate content to avoid hitting Telegram message length limits
            content_preview = mention.content[:100].replace('\n', ' ')
            if len(mention.content) > 100:
                content_preview += "..."
            
            message += f"Текст: {content_preview}\n\n"
        
        if len(mentions) > 5:
            message += f"...и еще {len(mentions) - 5} упоминаний\n"
        
        # Send Telegram message
        api_url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
        params = {
            "chat_id": settings.notification_telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        response = requests.post(api_url, json=params)
        data = response.json()
        
        if response.status_code == 200 and data.get("ok"):
            save_log(f"Telegram notification sent successfully to chat {settings.notification_telegram_chat_id}")
            return True
        else:
            error_message = data.get("description", "Unknown error")
            save_log(f"Failed to send Telegram notification: {error_message}", level="ERROR")
            return False
    
    except Exception as e:
        save_log(f"Error sending Telegram notification: {str(e)}", level="ERROR")
        return False

def send_notifications(project_id, mentions):
    """
    Send notifications about new mentions via configured channels
    
    Args:
        project_id (int): Project ID
        mentions (list): List of Mention objects
    
    Returns:
        dict: Dictionary with notification status for each channel
    """
    if not mentions:
        return {"email": False, "telegram": False}
    
    results = {
        "email": False,
        "telegram": False
    }
    
    # Send email notification
    results["email"] = send_email_notification(project_id, mentions)
    
    # Send Telegram notification
    results["telegram"] = send_telegram_notification(project_id, mentions)
    
    return results