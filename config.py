import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'gaav-asara-news-secret-key-2026')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'asara_news.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg'}

    # AI Moderation thresholds
    AUTO_PUBLISH_THRESHOLD = 40      # 0-40 → auto publish for trusted reporters
    REVIEW_THRESHOLD = 70            # 41-70 → admin review
    HOLD_THRESHOLD = 71              # 71+ → hold & notify admin

    # Risk weights (must sum to 1.0)
    SIMILARITY_WEIGHT = 0.30
    AI_DETECTION_WEIGHT = 0.25
    KEYWORD_WEIGHT = 0.25
    USER_BEHAVIOR_WEIGHT = 0.20

    # Similarity threshold for duplicate detection
    SIMILARITY_THRESHOLD = 0.75

    # Strike system
    TEMP_SUSPENSION_STRIKES = 3
    PERMANENT_BAN_STRIKES = 5
    TEMP_SUSPENSION_DAYS = 7

    # Pagination
    NEWS_PER_PAGE = 12
    ADMIN_PER_PAGE = 20
    COMMENTS_PER_PAGE = 10

    # Rate limiting
    MAX_SUBMISSIONS_PER_HOUR = 5
    MAX_COMMENTS_PER_MINUTE = 3

    # Suspicious keywords (configurable by super admin)
    SUSPICIOUS_KEYWORDS = [
        'fake', 'fraud', 'scam', 'conspiracy', 'hoax', 'clickbait',
        'urgent money', 'forward to all', 'share before deleted',
        'government hiding', 'secret exposed', 'shocking truth',
        'you won\'t believe', 'exposed', 'leaked'
    ]
