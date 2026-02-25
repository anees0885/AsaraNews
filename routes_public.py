"""
Public Routes – Homepage, Categories, Search, Events, Polls, Legal Pages
"""

from flask import Blueprint, render_template, request, redirect, url_for
from models import db, News, Category, Event, Poll, PollVote
from utils import paginate_query, get_client_ip
from flask_login import current_user
from datetime import datetime

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    """Homepage – Breaking news, trending, latest, categories."""
    page = request.args.get('page', 1, type=int)

    # Breaking / latest news
    breaking_news = News.query.filter_by(status='approved').order_by(
        News.created_at.desc()
    ).limit(5).all()

    # Trending (most viewed)
    trending = News.query.filter_by(status='approved').order_by(
        News.view_count.desc()
    ).limit(6).all()

    # Latest news with pagination
    latest_pagination = News.query.filter_by(status='approved').order_by(
        News.created_at.desc()
    ).paginate(page=page, per_page=12, error_out=False)

    # Active categories
    categories = Category.query.filter_by(is_active=True).order_by(
        Category.priority.asc()
    ).all()

    # Active polls
    active_polls = Poll.query.filter_by(is_active=True).all()
    polls = [p for p in active_polls if not p.is_expired][:3]

    # Upcoming events
    upcoming_events = Event.query.filter(
        Event.event_date >= datetime.utcnow(),
        Event.is_active == True
    ).order_by(Event.event_date.asc()).limit(5).all()

    return render_template('index.html',
        breaking_news=breaking_news,
        trending=trending,
        latest=latest_pagination,
        categories=categories,
        polls=polls,
        upcoming_events=upcoming_events
    )


@public_bp.route('/category/<slug>')
def category(slug):
    """Category listing page."""
    cat = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    page = request.args.get('page', 1, type=int)

    news_pagination = News.query.filter_by(
        category_id=cat.id, status='approved'
    ).order_by(News.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    categories = Category.query.filter_by(is_active=True).order_by(Category.priority.asc()).all()

    return render_template('category.html',
        category=cat,
        news=news_pagination,
        categories=categories
    )


@public_bp.route('/search')
def search():
    """Search and filter news."""
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    location = request.args.get('location', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    reporter_id = request.args.get('reporter', type=int)
    page = request.args.get('page', 1, type=int)

    news_query = News.query.filter_by(status='approved')

    if query:
        news_query = news_query.filter(
            db.or_(
                News.title.ilike(f'%{query}%'),
                News.content.ilike(f'%{query}%'),
                News.description.ilike(f'%{query}%'),
                News.tags.ilike(f'%{query}%')
            )
        )

    if category_id:
        news_query = news_query.filter_by(category_id=category_id)

    if location:
        news_query = news_query.filter(News.location.ilike(f'%{location}%'))

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            news_query = news_query.filter(News.created_at >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d')
            news_query = news_query.filter(News.created_at <= dt)
        except ValueError:
            pass

    if reporter_id:
        news_query = news_query.filter_by(author_id=reporter_id)

    news_pagination = news_query.order_by(News.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    categories = Category.query.filter_by(is_active=True).order_by(Category.priority.asc()).all()

    return render_template('search.html',
        news=news_pagination,
        query=query,
        categories=categories,
        selected_category=category_id,
        location=location,
        date_from=date_from,
        date_to=date_to
    )


@public_bp.route('/events')
def events():
    """Events calendar page."""
    upcoming = Event.query.filter(
        Event.event_date >= datetime.utcnow(),
        Event.is_active == True
    ).order_by(Event.event_date.asc()).all()

    past = Event.query.filter(
        Event.event_date < datetime.utcnow(),
        Event.is_active == True
    ).order_by(Event.event_date.desc()).limit(10).all()

    return render_template('events.html', upcoming=upcoming, past=past)


@public_bp.route('/polls')
def polls():
    """Public polls page."""
    active_polls = Poll.query.filter_by(is_active=True).order_by(
        Poll.created_at.desc()
    ).all()
    polls = [p for p in active_polls if not p.is_expired]
    return render_template('polls.html', polls=polls)


@public_bp.route('/terms')
def terms():
    return render_template('legal/terms.html')


@public_bp.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')


@public_bp.route('/disclaimer')
def disclaimer():
    return render_template('legal/disclaimer.html')
