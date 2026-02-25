"""
Admin Dashboard Routes – Moderation, Users, Categories, Events, Polls, Analytics, Settings
"""

import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import (db, User, News, Category, Comment, Event, Poll, PollVote,
                    ModerationLog, AuditLog, NewsReport, Notification)
from utils import role_required, save_uploaded_file, generate_unique_slug, log_audit, send_notification
from slugify import slugify

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
@login_required
def check_admin():
    if current_user.role not in ('admin', 'super_admin'):
        flash('Access denied.', 'error')
        return redirect(url_for('public.index'))


# ─── Dashboard ─────────────────────────────────────────────────
@admin_bp.route('/')
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'total_reporters': User.query.filter_by(role='reporter').count(),
        'total_news': News.query.count(),
        'pending_news': News.query.filter_by(status='pending').count(),
        'approved_news': News.query.filter_by(status='approved').count(),
        'rejected_news': News.query.filter_by(status='rejected').count(),
        'total_comments': Comment.query.count(),
        'total_events': Event.query.count(),
        'active_polls': Poll.query.filter_by(is_active=True).count(),
        'reports_pending': NewsReport.query.filter_by(status='pending').count(),
    }

    # High risk alerts
    high_risk = News.query.filter(
        News.final_risk_score >= 70, News.status == 'pending'
    ).order_by(News.final_risk_score.desc()).limit(5).all()

    # Recent activity
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(15).all()

    # Pending moderation
    pending = News.query.filter_by(status='pending').order_by(
        News.final_risk_score.desc()
    ).limit(10).all()

    # Today's submissions
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stats['today_submissions'] = News.query.filter(News.created_at >= today).count()

    return render_template('admin/dashboard.html', stats=stats, high_risk=high_risk,
                           recent_logs=recent_logs, pending=pending)


# ─── Moderation Queue ────────────────────────────────────────
@admin_bp.route('/moderation')
def moderation():
    status_filter = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)

    query = News.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    news = query.order_by(News.final_risk_score.desc(), News.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/moderation.html', news=news, status_filter=status_filter)


@admin_bp.route('/moderation/<int:news_id>/<action>', methods=['POST'])
def moderate_action(news_id, action):
    article = News.query.get_or_404(news_id)
    notes = request.form.get('notes', '')

    if action == 'approve':
        article.status = 'approved'
        send_notification(article.author_id, 'submission_status', 'News Approved',
                         f'Your article "{article.title}" has been approved!', f'/news/{article.slug}')
    elif action == 'reject':
        article.status = 'rejected'
        send_notification(article.author_id, 'submission_status', 'News Rejected',
                         f'Your article "{article.title}" was rejected. Reason: {notes}', None)
    elif action == 'archive':
        article.status = 'archived'
    elif action == 'takedown':
        article.status = 'rejected'
        # Emergency takedown - add strike
        author = User.query.get(article.author_id)
        if author:
            author.strike_count += 1
            _check_strikes(author)
            send_notification(author.id, 'strike', 'Strike Issued',
                            f'You received a strike for "{article.title}". Strikes: {author.strike_count}', None)

    mod_log = ModerationLog(
        news_id=news_id,
        admin_id=current_user.id,
        action=action,
        notes=notes,
        risk_score=article.final_risk_score
    )
    db.session.add(mod_log)
    db.session.commit()

    log_audit(current_user.id, f'news_{action}', f'{action.title()} news #{news_id}: {article.title}')
    flash(f'News {action}d successfully.', 'success')
    return redirect(url_for('admin.moderation'))


# ─── User Management ─────────────────────────────────────────
@admin_bp.route('/users')
def users():
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    search = request.args.get('q', '')

    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if search:
        query = query.filter(
            db.or_(User.username.ilike(f'%{search}%'), User.phone.ilike(f'%{search}%'))
        )

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users, role_filter=role_filter, search=search)


@admin_bp.route('/users/<int:user_id>/action', methods=['POST'])
def user_action(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')

    if action == 'verify_reporter':
        user.role = 'reporter'
        send_notification(user.id, 'admin_alert', 'Reporter Status Approved',
                         'You are now a verified reporter!', None)
    elif action == 'make_admin':
        if current_user.role != 'super_admin':
            flash('Only super admin can promote to admin.', 'error')
            return redirect(url_for('admin.users'))
        user.role = 'admin'
    elif action == 'suspend':
        user.is_suspended = True
        user.suspension_until = datetime.utcnow() + timedelta(days=current_app.config.get('TEMP_SUSPENSION_DAYS', 7))
        send_notification(user.id, 'admin_alert', 'Account Suspended',
                         f'Your account has been suspended until {user.suspension_until.strftime("%d %b %Y")}.', None)
    elif action == 'ban':
        user.is_banned = True
        send_notification(user.id, 'admin_alert', 'Account Banned',
                         'Your account has been permanently banned.', None)
    elif action == 'unsuspend':
        user.is_suspended = False
        user.suspension_until = None
    elif action == 'unban':
        user.is_banned = False
    elif action == 'reset_strikes':
        user.strike_count = 0
    elif action == 'demote':
        user.role = 'registered'
    elif action == 'add_strike':
        user.strike_count += 1
        _check_strikes(user)
        send_notification(user.id, 'strike', 'Strike Issued',
                         f'You received a strike. Total: {user.strike_count}', None)

    db.session.commit()
    log_audit(current_user.id, f'user_{action}', f'{action} on user {user.username} (ID: {user.id})')
    flash(f'Action "{action}" applied to {user.username}.', 'success')
    return redirect(url_for('admin.users'))


def _check_strikes(user):
    """Check strike count and apply suspensions/bans."""
    config = current_app.config
    if user.strike_count >= config.get('PERMANENT_BAN_STRIKES', 5):
        user.is_banned = True
    elif user.strike_count >= config.get('TEMP_SUSPENSION_STRIKES', 3):
        user.is_suspended = True
        user.suspension_until = datetime.utcnow() + timedelta(days=config.get('TEMP_SUSPENSION_DAYS', 7))


# ─── Category Management ─────────────────────────────────────
@admin_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        icon = request.form.get('icon', '📰').strip()
        priority = request.form.get('priority', 0, type=int)
        description = request.form.get('description', '').strip()

        if not name:
            flash('Category name is required.', 'error')
        elif Category.query.filter_by(name=name).first():
            flash('Category already exists.', 'error')
        else:
            cat = Category(
                name=name,
                slug=slugify(name),
                icon=icon,
                priority=priority,
                description=description
            )
            db.session.add(cat)
            db.session.commit()
            log_audit(current_user.id, 'category_created', f'Created category: {name}')
            flash(f'Category "{name}" created.', 'success')

    cats = Category.query.order_by(Category.priority.asc()).all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
def edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.name = request.form.get('name', cat.name).strip()
    cat.icon = request.form.get('icon', cat.icon).strip()
    cat.priority = request.form.get('priority', cat.priority, type=int)
    cat.description = request.form.get('description', '').strip()
    cat.is_active = request.form.get('is_active') == 'on'
    cat.slug = slugify(cat.name)
    db.session.commit()
    log_audit(current_user.id, 'category_edited', f'Edited category: {cat.name}')
    flash(f'Category "{cat.name}" updated.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    name = cat.name
    db.session.delete(cat)
    db.session.commit()
    log_audit(current_user.id, 'category_deleted', f'Deleted category: {name}')
    flash(f'Category "{name}" deleted.', 'success')
    return redirect(url_for('admin.categories'))


# ─── Event Management ────────────────────────────────────────
@admin_bp.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date_str = request.form.get('event_date', '')
        event_time = request.form.get('event_time', '')
        location = request.form.get('location', '').strip()
        reminder = request.form.get('reminder_enabled') == 'on'

        if not title or not event_date_str or not location:
            flash('Title, date, and location are required.', 'error')
        else:
            event = Event(
                title=title,
                description=description,
                event_date=datetime.strptime(event_date_str, '%Y-%m-%d'),
                event_time=event_time,
                location=location,
                reminder_enabled=reminder,
                created_by=current_user.id
            )
            if 'image' in request.files:
                file = request.files['image']
                if file.filename:
                    event.image = save_uploaded_file(file, 'events')

            db.session.add(event)
            db.session.commit()
            log_audit(current_user.id, 'event_created', f'Created event: {title}')
            flash(f'Event "{title}" created.', 'success')

    events_list = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('admin/events.html', events=events_list)


@admin_bp.route('/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    name = event.title
    db.session.delete(event)
    db.session.commit()
    log_audit(current_user.id, 'event_deleted', f'Deleted event: {name}')
    flash(f'Event "{name}" deleted.', 'success')
    return redirect(url_for('admin.events'))


# ─── Poll Management ─────────────────────────────────────────
@admin_bp.route('/polls', methods=['GET', 'POST'])
def polls():
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        options_str = request.form.get('options', '').strip()
        expires_str = request.form.get('expires_at', '')
        ip_restrict = request.form.get('ip_restriction') == 'on'

        options = [o.strip() for o in options_str.split('\n') if o.strip()]

        if not question or len(options) < 2:
            flash('Question and at least 2 options required.', 'error')
        else:
            poll = Poll(
                question=question,
                options=json.dumps(options),
                created_by=current_user.id,
                ip_restriction=ip_restrict
            )
            if expires_str:
                try:
                    poll.expires_at = datetime.strptime(expires_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass

            db.session.add(poll)
            db.session.commit()
            log_audit(current_user.id, 'poll_created', f'Created poll: {question}')
            flash('Poll created.', 'success')

    polls_list = Poll.query.order_by(Poll.created_at.desc()).all()
    return render_template('admin/polls.html', polls=polls_list)


@admin_bp.route('/polls/<int:poll_id>/toggle', methods=['POST'])
def toggle_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    poll.is_active = not poll.is_active
    db.session.commit()
    flash(f'Poll {"activated" if poll.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.polls'))


# ─── Reports (Reported Content) ──────────────────────────────
@admin_bp.route('/reports')
def reports():
    page = request.args.get('page', 1, type=int)
    reports = NewsReport.query.order_by(NewsReport.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/reports.html', reports=reports)


@admin_bp.route('/reports/<int:report_id>/action', methods=['POST'])
def report_action(report_id):
    report = NewsReport.query.get_or_404(report_id)
    action = request.form.get('action')

    if action == 'dismiss':
        report.status = 'dismissed'
    elif action == 'reviewed':
        report.status = 'reviewed'
    elif action == 'takedown':
        report.status = 'reviewed'
        news = News.query.get(report.news_id)
        if news:
            news.status = 'rejected'

    db.session.commit()
    flash('Report updated.', 'success')
    return redirect(url_for('admin.reports'))


# ─── Analytics ────────────────────────────────────────────────
@admin_bp.route('/analytics')
def analytics():
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    stats = {
        'total_users': User.query.count(),
        'total_reporters': User.query.filter_by(role='reporter').count(),
        'new_users_7d': User.query.filter(User.created_at >= seven_days_ago).count(),
        'total_news': News.query.filter_by(status='approved').count(),
        'news_30d': News.query.filter(News.created_at >= thirty_days_ago).count(),
        'approval_ratio': _get_approval_ratio(),
        'total_views': db.session.query(db.func.sum(News.view_count)).scalar() or 0,
        'total_likes': db.session.query(db.func.sum(News.like_count)).scalar() or 0,
        'total_comments': Comment.query.count(),
    }

    # Most viewed news
    most_viewed = News.query.filter_by(status='approved').order_by(
        News.view_count.desc()
    ).limit(10).all()

    # Category distribution
    categories = Category.query.all()
    cat_stats = []
    for cat in categories:
        count = News.query.filter_by(category_id=cat.id, status='approved').count()
        cat_stats.append({'name': cat.name, 'icon': cat.icon, 'count': count})
    cat_stats.sort(key=lambda x: x['count'], reverse=True)

    # Daily submissions (last 30 days)
    daily_data = []
    for i in range(30):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = News.query.filter(News.created_at >= day_start, News.created_at < day_end).count()
        daily_data.append({'date': day_start.strftime('%d %b'), 'count': count})
    daily_data.reverse()

    return render_template('admin/analytics.html', stats=stats, most_viewed=most_viewed,
                           cat_stats=cat_stats, daily_data=daily_data)


def _get_approval_ratio():
    total = News.query.filter(News.status.in_(['approved', 'rejected'])).count()
    if total == 0:
        return 0
    approved = News.query.filter_by(status='approved').count()
    return round((approved / total) * 100, 1)


# ─── System Logs (Super Admin) ───────────────────────────────
@admin_bp.route('/logs')
@role_required('super_admin')
def logs():
    page = request.args.get('page', 1, type=int)
    audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('admin/settings.html', logs=audit_logs)


# ─── Settings (Super Admin) ──────────────────────────────────
@admin_bp.route('/settings', methods=['GET', 'POST'])
@role_required('super_admin')
def settings():
    if request.method == 'POST':
        # Update AI thresholds (in session for demo; production would use DB/env)
        new_auto = request.form.get('auto_threshold', type=int)
        new_review = request.form.get('review_threshold', type=int)
        if new_auto and new_review:
            current_app.config['AUTO_PUBLISH_THRESHOLD'] = new_auto
            current_app.config['REVIEW_THRESHOLD'] = new_review
            current_app.config['HOLD_THRESHOLD'] = new_review + 1
            flash('AI thresholds updated.', 'success')
            log_audit(current_user.id, 'settings_updated', f'AI thresholds: auto={new_auto}, review={new_review}')

    page = request.args.get('page', 1, type=int)
    audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('admin/settings.html', logs=audit_logs, config=current_app.config)
