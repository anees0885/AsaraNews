"""
API Routes – JSON endpoints for AJAX interactions
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, News, Poll, PollVote, Notification
from utils import get_client_ip

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/notifications/count')
@login_required
def notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


@api_bp.route('/notifications')
@login_required
def get_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(10).all()

    return jsonify({
        'notifications': [
            {
                'id': n.id,
                'type': n.type,
                'title': n.title,
                'message': n.message,
                'link': n.link,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d %b %Y, %H:%M')
            } for n in notifs
        ]
    })


@api_bp.route('/poll/<int:poll_id>/results')
def poll_results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    results, total = poll.get_results()
    return jsonify({'results': results, 'total': total, 'question': poll.question})


@api_bp.route('/search/suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'suggestions': []})

    news = News.query.filter(
        News.title.ilike(f'%{q}%'),
        News.status == 'approved'
    ).limit(5).all()

    suggestions = [{'title': n.title, 'slug': n.slug} for n in news]
    return jsonify({'suggestions': suggestions})
