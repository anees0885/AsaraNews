"""
Asara News – Main Application
───────────────────────────────────
Village news platform with AI moderation & live streaming
"""

import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_socketio import SocketIO
from config import Config
from models import db, User
from moderation import get_moderation_engine

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'news'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'news', 'gallery'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'events'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'posts'), exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Init moderation engine
    get_moderation_engine(app.config)

    # Register blueprints
    from auth import auth_bp
    from routes_public import public_bp
    from routes_news import news_bp
    from routes_admin import admin_bp
    from routes_reporter import reporter_bp
    from routes_api import api_bp
    from routes_community import community_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reporter_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(community_bp)

    # Init SocketIO events
    from socketio_events import register_socketio_events
    register_socketio_events(socketio)

    # Template context processor
    @app.context_processor
    def inject_globals():
        from models import Category, Notification
        from flask_login import current_user
        categories = Category.query.filter_by(is_active=True).order_by(Category.priority.asc()).all()
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(all_categories=categories, unread_notifications=unread)

    # Custom template filters
    @app.template_filter('timeago')
    def timeago_filter(dt):
        from utils import format_datetime
        return format_datetime(dt)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # Create tables
    with app.app_context():
        db.create_all()

    return app


socketio = SocketIO(cors_allowed_origins='*')
app = create_app()
socketio.init_app(app)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
