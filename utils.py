import os
import uuid
import re
from functools import wraps
from datetime import datetime
from flask import request, abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from slugify import slugify


def role_required(*roles):
    """Decorator to restrict access based on user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            if not current_user.is_active_account:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def save_uploaded_file(file, subfolder='images'):
    """Save uploaded file and return the relative path."""
    if not file:
        return None

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    allowed = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', set())
    allowed_video = current_app.config.get('ALLOWED_VIDEO_EXTENSIONS', set())

    if ext not in allowed and ext not in allowed_video:
        return None

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, unique_name)
    file.save(filepath)

    return f"uploads/{subfolder}/{unique_name}"


def generate_unique_slug(title, model_class):
    """Generate a unique slug for a given title."""
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    while model_class.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def paginate_query(query, page, per_page):
    """Paginate a SQLAlchemy query."""
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return pagination


def get_client_ip():
    """Get the client's IP address."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr


def get_device_info():
    """Get basic device info from user agent."""
    return request.headers.get('User-Agent', 'Unknown')[:256]


def log_audit(user_id, action, details=None):
    """Log an audit trail entry."""
    from models import AuditLog, db
    log = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=get_client_ip(),
        device_info=get_device_info()
    )
    db.session.add(log)
    db.session.commit()


def send_notification(user_id, notif_type, title, message, link=None):
    """Create a notification for a user."""
    from models import Notification, db
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link
    )
    db.session.add(notif)
    db.session.commit()


def sanitize_html(text):
    """Basic HTML sanitization - strips all tags."""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()


def format_datetime(dt):
    """Format datetime for display."""
    if not dt:
        return ''
    now = datetime.utcnow()
    diff = now - dt
    if diff.days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            minutes = diff.seconds // 60
            if minutes == 0:
                return 'Just now'
            return f'{minutes}m ago'
        return f'{hours}h ago'
    elif diff.days == 1:
        return 'Yesterday'
    elif diff.days < 7:
        return f'{diff.days}d ago'
    return dt.strftime('%d %b %Y')


def allowed_file(filename, file_type='image'):
    """Check if a file extension is allowed."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'image':
        return ext in current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', set())
    elif file_type == 'video':
        return ext in current_app.config.get('ALLOWED_VIDEO_EXTENSIONS', set())
    return False
