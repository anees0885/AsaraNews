"""
Routes for Go Live and Create Post features
"""
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, LiveStream, Post
from utils import save_uploaded_file, log_audit

community_bp = Blueprint('community', __name__, url_prefix='/community')


# ─── Go Live ──────────────────────────────────────────────────
@community_bp.route('/go-live', methods=['GET', 'POST'])
@login_required
def go_live():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Please provide a title for your live stream.', 'error')
            return redirect(url_for('community.go_live'))

        stream_key = str(uuid.uuid4())[:12].replace('-', '')

        stream = LiveStream(
            title=title,
            description=description,
            user_id=current_user.id,
            stream_key=stream_key,
            status='live'
        )
        db.session.add(stream)
        db.session.commit()

        log_audit(current_user.id, 'go_live', f'Started live stream: {title}')
        flash('You are now LIVE! Share your stream with others.', 'success')
        return redirect(url_for('community.stream_view', stream_id=stream.id))

    return render_template('community/go_live.html')


@community_bp.route('/stream/<int:stream_id>')
def stream_view(stream_id):
    stream = LiveStream.query.get_or_404(stream_id)
    if stream.status == 'live':
        stream.viewer_count += 1
        if stream.viewer_count > stream.peak_viewers:
            stream.peak_viewers = stream.viewer_count
        db.session.commit()
    return render_template('community/stream_view.html', stream=stream)


@community_bp.route('/stream/<int:stream_id>/end', methods=['POST'])
@login_required
def end_stream(stream_id):
    stream = LiveStream.query.get_or_404(stream_id)
    if stream.user_id != current_user.id:
        flash('You can only end your own stream.', 'error')
        return redirect(url_for('public.index'))

    stream.status = 'ended'
    stream.ended_at = datetime.utcnow()
    db.session.commit()

    log_audit(current_user.id, 'end_live', f'Ended live stream: {stream.title}')
    flash('Live stream ended successfully.', 'success')
    return redirect(url_for('public.index'))


@community_bp.route('/live')
def live_streams():
    active = LiveStream.query.filter_by(status='live').order_by(LiveStream.started_at.desc()).all()
    past = LiveStream.query.filter_by(status='ended').order_by(LiveStream.ended_at.desc()).limit(10).all()
    return render_template('community/live_list.html', active_streams=active, past_streams=past)


# ─── Create Post ──────────────────────────────────────────────
@community_bp.route('/create-post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()

        if not content:
            flash('Post content cannot be empty.', 'error')
            return redirect(url_for('community.create_post'))

        if len(content) > 1000:
            flash('Post must be under 1000 characters.', 'error')
            return redirect(url_for('community.create_post'))

        post = Post(
            content=content,
            user_id=current_user.id
        )

        # Handle optional image
        if 'image' in request.files and request.files['image'].filename:
            filename = save_uploaded_file(request.files['image'], 'posts')
            if filename:
                post.image = filename

        db.session.add(post)
        db.session.commit()

        log_audit(current_user.id, 'create_post', f'Created post #{post.id}')
        flash('Post published successfully!', 'success')
        return redirect(url_for('community.posts_feed'))

    return render_template('community/create_post.html')


@community_bp.route('/posts')
def posts_feed():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_active=True)\
        .order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('community/posts_feed.html', posts=posts)


@community_bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.like_count += 1
    db.session.commit()
    return jsonify({'likes': post.like_count})


@community_bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and current_user.role not in ('admin', 'super_admin'):
        flash('Unauthorized.', 'error')
        return redirect(url_for('community.posts_feed'))

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('community.posts_feed'))
