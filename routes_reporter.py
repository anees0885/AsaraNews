"""
Reporter Dashboard Routes – Stats, Submissions, Notifications
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, News, Notification, ModerationLog
from utils import role_required

reporter_bp = Blueprint('reporter', __name__, url_prefix='/reporter')


@reporter_bp.before_request
@login_required
def check_reporter():
    if current_user.role not in ('reporter', 'admin', 'super_admin'):
        flash('Reporter access required.', 'error')
        return redirect(url_for('public.index'))


@reporter_bp.route('/')
def dashboard():
    """Reporter dashboard with stats and submissions."""
    stats = {
        'total_submissions': News.query.filter_by(author_id=current_user.id).count(),
        'approved': News.query.filter_by(author_id=current_user.id, status='approved').count(),
        'rejected': News.query.filter_by(author_id=current_user.id, status='rejected').count(),
        'pending': News.query.filter_by(author_id=current_user.id, status='pending').count(),
        'total_views': sum(n.view_count for n in News.query.filter_by(author_id=current_user.id, status='approved').all()),
        'total_likes': sum(n.like_count for n in News.query.filter_by(author_id=current_user.id, status='approved').all()),
        'total_comments': sum(n.comment_count for n in News.query.filter_by(author_id=current_user.id, status='approved').all()),
        'strike_count': current_user.strike_count,
    }

    # Recent submissions
    submissions = News.query.filter_by(author_id=current_user.id).order_by(
        News.created_at.desc()
    ).limit(20).all()

    # Top performing
    top_news = News.query.filter_by(
        author_id=current_user.id, status='approved'
    ).order_by(News.view_count.desc()).limit(5).all()

    # Unread notifications
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()

    return render_template('reporter/dashboard.html',
        stats=stats,
        submissions=submissions,
        top_news=top_news,
        unread_count=unread_count
    )


@reporter_bp.route('/notifications')
def notifications():
    """Notification center."""
    page = request.args.get('page', 1, type=int)
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('reporter/dashboard.html',
        show_notifications=True,
        notifications=notifs,
        stats={
            'total_submissions': News.query.filter_by(author_id=current_user.id).count(),
            'approved': News.query.filter_by(author_id=current_user.id, status='approved').count(),
            'rejected': News.query.filter_by(author_id=current_user.id, status='rejected').count(),
            'pending': News.query.filter_by(author_id=current_user.id, status='pending').count(),
            'total_views': 0,
            'total_likes': 0,
            'total_comments': 0,
            'strike_count': current_user.strike_count,
        },
        submissions=[],
        top_news=[],
        unread_count=0
    )


@reporter_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})
