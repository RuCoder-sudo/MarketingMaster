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
from social_api import search_vk, search_ok
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
            
            # Update or create settings
            settings = Settings.query.filter_by(project_id=active_project.id).first()
            if not settings:
                settings = Settings(project_id=active_project.id)
                db.session.add(settings)
            
            settings.vk_token = vk_token
            settings.ok_token = ok_token
            settings.ok_public_key = ok_public_key
            settings.ok_private_key = ok_private_key
            
            db.session.commit()
            flash('API tokens saved successfully!', 'success')
            save_log(f"API tokens updated for project {active_project.name}")
            
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
                
                db.session.commit()
                flash(f'Community ID {community_id} removed from {social_network.upper()} monitoring!', 'success')
                save_log(f"Removed {social_network} community {community_id} from project {active_project.name}")
            
        return redirect(url_for('settings'))
    
    # Get current settings
    settings = Settings.query.filter_by(project_id=active_project.id).first()
    vk_communities = []
    ok_communities = []
    
    if settings:
        if settings.vk_communities:
            vk_communities = settings.vk_communities.split(',')
        if settings.ok_communities:
            ok_communities = settings.ok_communities.split(',')
    
    return render_template('settings.html', 
                          active_project=active_project,
                          settings=settings,
                          vk_communities=vk_communities,
                          ok_communities=ok_communities)

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
                flash('You need to set up API tokens in Settings first!', 'danger')
                return redirect(url_for('search'))
            
            # Check if we have keywords
            if not keywords:
                flash('You need to add at least one keyword before searching!', 'danger')
                return redirect(url_for('search'))
            
            # Perform manual search
            try:
                if settings.vk_token and settings.vk_communities:
                    # VK search
                    vk_communities = settings.vk_communities.split(',')
                    for community_id in vk_communities:
                        search_vk(active_project.id, community_id, [k.keyword for k in keywords])
                
                if settings.ok_token and settings.ok_communities:
                    # OK search
                    ok_communities = settings.ok_communities.split(',')
                    for community_id in ok_communities:
                        search_ok(active_project.id, community_id, [k.keyword for k in keywords])
                
                flash('Manual search completed successfully!', 'success')
                save_log(f"Performed manual search for project {active_project.name}")
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
