from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json

db = SQLAlchemy()

# ─── User Model ───────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='registered')  # guest, registered, reporter, admin, super_admin
    profile_pic = db.Column(db.String(256), default='default_avatar.png')
    bio = db.Column(db.Text, nullable=True)

    is_verified = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    suspension_until = db.Column(db.DateTime, nullable=True)
    strike_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    last_ip = db.Column(db.String(45), nullable=True)
    last_device = db.Column(db.String(256), nullable=True)

    # Relationships
    news_articles = db.relationship('News', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active_account(self):
        if self.is_banned:
            return False
        if self.is_suspended and self.suspension_until:
            if datetime.utcnow() < self.suspension_until:
                return False
            else:
                self.is_suspended = False
                self.suspension_until = None
        return True

    def __repr__(self):
        return f'<User {self.username}>'


# ─── OTP Model ────────────────────────────────────────────────
class OTP(db.Model):
    __tablename__ = 'otps'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

    def is_valid(self):
        return not self.is_used and datetime.utcnow() < self.expires_at


# ─── Category Model ───────────────────────────────────────────
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    icon = db.Column(db.String(50), default='📰')
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    news_articles = db.relationship('News', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


# ─── News Model ───────────────────────────────────────────────
class News(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(256), nullable=True)
    video_url = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.DateTime, nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated

    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, archived
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)

    # AI Moderation scores
    ai_score = db.Column(db.Float, default=0.0)          # AI-generated text probability
    similarity_score = db.Column(db.Float, default=0.0)   # Duplicate detection score
    keyword_score = db.Column(db.Float, default=0.0)      # Suspicious keyword score
    final_risk_score = db.Column(db.Float, default=0.0)   # Combined risk 0-100
    moderation_decision = db.Column(db.String(50), nullable=True)  # auto_published, review, hold

    # Embedding for similarity search (stored as JSON string of TF-IDF vector)
    content_embedding = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    images = db.relationship('NewsImage', backref='news', lazy='dynamic', cascade='all, delete-orphan')
    comments_list = db.relationship('Comment', backref='news', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('NewsLike', backref='news', lazy='dynamic', cascade='all, delete-orphan')
    reports = db.relationship('NewsReport', backref='news', lazy='dynamic', cascade='all, delete-orphan')
    moderation_logs = db.relationship('ModerationLog', backref='news', lazy='dynamic', cascade='all, delete-orphan')

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',')]
        return []

    def __repr__(self):
        return f'<News {self.title[:50]}>'


# ─── News Image Gallery ───────────────────────────────────────
class NewsImage(db.Model):
    __tablename__ = 'news_images'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    image_path = db.Column(db.String(256), nullable=False)
    caption = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Comment Model ────────────────────────────────────────────
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True)
    is_reported = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Comment by User {self.user_id}>'


# ─── News Like ────────────────────────────────────────────────
class NewsLike(db.Model):
    __tablename__ = 'news_likes'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('news_id', 'user_id', name='unique_news_like'),)


# ─── News Report ──────────────────────────────────────────────
class NewsReport(db.Model):
    __tablename__ = 'news_reports'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, dismissed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', backref='filed_reports')


# ─── Poll Model ───────────────────────────────────────────────
class Poll(db.Model):
    __tablename__ = 'polls'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON array of option strings
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_restriction = db.Column(db.Boolean, default=False)  # One vote per IP

    votes = db.relationship('PollVote', backref='poll', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', backref='created_polls')

    def get_options(self):
        return json.loads(self.options)

    def get_results(self):
        options = self.get_options()
        results = []
        total_votes = self.votes.count()
        for i, option in enumerate(options):
            count = self.votes.filter_by(option_index=i).count()
            pct = round((count / total_votes * 100), 1) if total_votes > 0 else 0
            results.append({'option': option, 'count': count, 'percentage': pct})
        return results, total_votes

    @property
    def is_expired(self):
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False


# ─── Poll Vote ────────────────────────────────────────────────
class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    option_index = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('poll_id', 'user_id', name='unique_poll_vote'),)


# ─── Event Model ──────────────────────────────────────────────
class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    event_time = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(256), nullable=True)
    reminder_enabled = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='created_events')

    @property
    def is_upcoming(self):
        return self.event_date > datetime.utcnow()


# ─── Moderation Log ───────────────────────────────────────────
class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # submitted, auto_published, approved, rejected, held, archived
    notes = db.Column(db.Text, nullable=True)
    risk_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', backref='moderation_actions')


# ─── Audit Log ─────────────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    device_info = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs')


# ─── Notification ─────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # submission_status, admin_alert, strike, event_reminder
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.type} for User {self.user_id}>'


# ─── Live Stream Model ────────────────────────────────────────
class LiveStream(db.Model):
    __tablename__ = 'live_streams'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(db.String(20), default='live')  # live, ended
    stream_key = db.Column(db.String(100), unique=True, nullable=False)
    viewer_count = db.Column(db.Integer, default=0)
    peak_viewers = db.Column(db.Integer, default=0)
    thumbnail = db.Column(db.String(256), nullable=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    streamer = db.relationship('User', backref='live_streams')

    def __repr__(self):
        return f'<LiveStream {self.title[:40]}>'


# ─── Post Model (Quick Updates) ──────────────────────────────
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(256), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    like_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='posts')

    def __repr__(self):
        return f'<Post by {self.user_id}>'
