"""
News Routes – Submit, Edit, View, Like, Comment, Report
"""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, News, Category, Comment, NewsLike, NewsReport, NewsImage, ModerationLog, Notification
from utils import (role_required, save_uploaded_file, generate_unique_slug,
                   get_client_ip, log_audit, send_notification, sanitize_html)
from moderation import get_moderation_engine

news_bp = Blueprint('news', __name__, url_prefix='/news')


@news_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    """Submit a new news article."""
    if not current_user.is_active_account:
        flash('Your account is suspended or banned.', 'error')
        return redirect(url_for('public.index'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.priority.asc()).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id', type=int)
        location = request.form.get('location', '').strip()
        event_date_str = request.form.get('event_date', '')
        tags = request.form.get('tags', '').strip()
        video_url = request.form.get('video_url', '').strip()

        # Validation
        errors = []
        if not title or len(title) < 10:
            errors.append('Title must be at least 10 characters.')
        if not description or len(description) < 20:
            errors.append('Description must be at least 20 characters.')
        if not content or len(content) < 50:
            errors.append('Content must be at least 50 characters.')
        if not category_id:
            errors.append('Please select a category.')
        if not location:
            errors.append('Location is required.')

        event_date = None
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
            except ValueError:
                errors.append('Invalid event date format.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('news/submit.html', categories=categories,
                                   title=title, description=description, content=content,
                                   location=location, tags=tags, video_url=video_url)

        # Sanitize
        title = sanitize_html(title)
        description = sanitize_html(description)

        # Featured image
        featured_image = None
        if 'featured_image' in request.files:
            file = request.files['featured_image']
            if file.filename:
                featured_image = save_uploaded_file(file, 'news')

        # Generate slug
        slug = generate_unique_slug(title, News)

        # Run AI moderation
        engine = get_moderation_engine(current_app.config)
        existing_texts = [n.content for n in News.query.filter_by(status='approved').all()]
        moderation = engine.analyze(title, content, description, current_user, existing_texts)

        # Create news article
        news = News(
            title=title,
            slug=slug,
            description=description,
            content=content,
            featured_image=featured_image,
            video_url=video_url,
            location=location,
            event_date=event_date,
            tags=tags,
            category_id=category_id,
            author_id=current_user.id,
            ai_score=moderation['ai_score'],
            similarity_score=moderation['similarity_score'],
            keyword_score=moderation['keyword_score'],
            final_risk_score=moderation['final_risk_score'],
            moderation_decision=moderation['moderation_decision'],
            content_embedding=moderation['content_embedding']
        )

        # Set status based on moderation
        if moderation['moderation_decision'] == 'auto_published':
            news.status = 'approved'
        else:
            news.status = 'pending'

        db.session.add(news)
        db.session.flush()  # Get news.id

        # Save gallery images
        gallery_files = request.files.getlist('gallery_images')
        for gf in gallery_files:
            if gf.filename:
                img_path = save_uploaded_file(gf, 'news/gallery')
                if img_path:
                    gallery_img = NewsImage(news_id=news.id, image_path=img_path)
                    db.session.add(gallery_img)

        # Moderation log
        mod_log = ModerationLog(
            news_id=news.id,
            action='submitted',
            notes=f"AI Risk: {moderation['final_risk_score']}, Decision: {moderation['moderation_decision']}. Flags: {'; '.join(moderation['flags'])}",
            risk_score=moderation['final_risk_score']
        )
        db.session.add(mod_log)

        db.session.commit()

        log_audit(current_user.id, 'news_submitted', f'Submitted news: {title} (Risk: {moderation["final_risk_score"]})')

        if moderation['moderation_decision'] == 'auto_published':
            flash('Your news has been published automatically!', 'success')
            send_notification(current_user.id, 'submission_status', 'News Published',
                            f'Your article "{title}" has been auto-published.', f'/news/{slug}')
        elif moderation['moderation_decision'] == 'review':
            flash('Your news has been submitted for admin review.', 'info')
            send_notification(current_user.id, 'submission_status', 'News Under Review',
                            f'Your article "{title}" is being reviewed by admin.', None)
        else:
            flash('Your news has been submitted and is on hold for review.', 'warning')
            send_notification(current_user.id, 'submission_status', 'News On Hold',
                            f'Your article "{title}" is on hold due to high risk score.', None)

        return redirect(url_for('public.index'))

    return render_template('news/submit.html', categories=categories)


@news_bp.route('/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
def edit(news_id):
    """Edit own pending/rejected news."""
    article = News.query.get_or_404(news_id)

    if article.author_id != current_user.id:
        flash('You can only edit your own submissions.', 'error')
        return redirect(url_for('public.index'))

    if article.status not in ('pending', 'rejected'):
        flash('You can only edit pending or rejected submissions.', 'error')
        return redirect(url_for('public.index'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.priority.asc()).all()

    if request.method == 'POST':
        article.title = sanitize_html(request.form.get('title', '').strip())
        article.description = sanitize_html(request.form.get('description', '').strip())
        article.content = request.form.get('content', '').strip()
        article.category_id = request.form.get('category_id', type=int)
        article.location = request.form.get('location', '').strip()
        article.tags = request.form.get('tags', '').strip()
        article.video_url = request.form.get('video_url', '').strip()

        event_date_str = request.form.get('event_date', '')
        if event_date_str:
            try:
                article.event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
            except ValueError:
                pass

        if 'featured_image' in request.files:
            file = request.files['featured_image']
            if file.filename:
                article.featured_image = save_uploaded_file(file, 'news')

        # Re-run moderation
        engine = get_moderation_engine(current_app.config)
        existing_texts = [n.content for n in News.query.filter(
            News.status == 'approved', News.id != article.id
        ).all()]
        moderation = engine.analyze(article.title, article.content, article.description,
                                     current_user, existing_texts)

        article.ai_score = moderation['ai_score']
        article.similarity_score = moderation['similarity_score']
        article.keyword_score = moderation['keyword_score']
        article.final_risk_score = moderation['final_risk_score']
        article.moderation_decision = moderation['moderation_decision']
        article.content_embedding = moderation['content_embedding']
        article.status = 'pending'
        article.updated_at = datetime.utcnow()

        mod_log = ModerationLog(
            news_id=article.id,
            action='resubmitted',
            notes=f"Re-moderated. Risk: {moderation['final_risk_score']}",
            risk_score=moderation['final_risk_score']
        )
        db.session.add(mod_log)
        db.session.commit()

        log_audit(current_user.id, 'news_edited', f'Edited and resubmitted: {article.title}')
        flash('Your news has been resubmitted for review.', 'info')
        return redirect(url_for('public.index'))

    return render_template('news/edit.html', article=article, categories=categories)


@news_bp.route('/<slug>')
def detail(slug):
    """Public news detail page."""
    article = News.query.filter_by(slug=slug, status='approved').first_or_404()

    # Increment view
    article.view_count += 1
    db.session.commit()

    # Comments
    comments = article.comments_list.filter_by(is_approved=True).order_by(
        Comment.created_at.desc()
    ).all()

    # Related news
    related = News.query.filter(
        News.category_id == article.category_id,
        News.id != article.id,
        News.status == 'approved'
    ).order_by(News.created_at.desc()).limit(4).all()

    # Check if user liked
    user_liked = False
    if current_user.is_authenticated:
        user_liked = NewsLike.query.filter_by(
            news_id=article.id, user_id=current_user.id
        ).first() is not None

    return render_template('news_detail.html',
        article=article,
        comments=comments,
        related=related,
        user_liked=user_liked
    )


@news_bp.route('/<int:news_id>/like', methods=['POST'])
@login_required
def like(news_id):
    """Like/unlike a news article."""
    article = News.query.get_or_404(news_id)
    existing = NewsLike.query.filter_by(news_id=news_id, user_id=current_user.id).first()

    if existing:
        db.session.delete(existing)
        article.like_count = max(0, article.like_count - 1)
        liked = False
    else:
        like = NewsLike(news_id=news_id, user_id=current_user.id)
        db.session.add(like)
        article.like_count += 1
        liked = True

    db.session.commit()
    return jsonify({'liked': liked, 'count': article.like_count})


@news_bp.route('/<int:news_id>/comment', methods=['POST'])
@login_required
def comment(news_id):
    """Add a comment to a news article."""
    article = News.query.get_or_404(news_id)
    content = request.form.get('content', '').strip()

    if not content or len(content) < 3:
        flash('Comment must be at least 3 characters.', 'error')
        return redirect(url_for('news.detail', slug=article.slug))

    content = sanitize_html(content)

    comment = Comment(
        news_id=news_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(comment)
    article.comment_count += 1
    db.session.commit()

    log_audit(current_user.id, 'comment_added', f'Commented on: {article.title}')
    flash('Comment posted!', 'success')
    return redirect(url_for('news.detail', slug=article.slug))


@news_bp.route('/<int:news_id>/report', methods=['POST'])
@login_required
def report(news_id):
    """Report a news article."""
    reason = request.form.get('reason', '').strip()

    if not reason:
        return jsonify({'error': 'Reason is required'}), 400

    existing = NewsReport.query.filter_by(news_id=news_id, reporter_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'You have already reported this article'}), 400

    report = NewsReport(
        news_id=news_id,
        reporter_id=current_user.id,
        reason=reason
    )
    db.session.add(report)
    db.session.commit()

    log_audit(current_user.id, 'news_reported', f'Reported news ID #{news_id}: {reason}')
    return jsonify({'success': True, 'message': 'Report submitted. Thank you.'})


@news_bp.route('/poll/<int:poll_id>/vote', methods=['POST'])
@login_required
def poll_vote(poll_id):
    """Vote on a poll."""
    poll = Poll.query.get_or_404(poll_id)
    from models import Poll, PollVote

    if poll.is_expired or not poll.is_active:
        return jsonify({'error': 'This poll has ended'}), 400

    option_index = request.form.get('option', type=int)
    if option_index is None or option_index < 0 or option_index >= len(poll.get_options()):
        return jsonify({'error': 'Invalid option'}), 400

    # Check existing vote
    existing = PollVote.query.filter_by(poll_id=poll_id, user_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'You have already voted'}), 400

    # IP check
    if poll.ip_restriction:
        ip_vote = PollVote.query.filter_by(poll_id=poll_id, ip_address=get_client_ip()).first()
        if ip_vote:
            return jsonify({'error': 'Already voted from this IP'}), 400

    vote = PollVote(
        poll_id=poll_id,
        user_id=current_user.id,
        option_index=option_index,
        ip_address=get_client_ip()
    )
    db.session.add(vote)
    db.session.commit()

    results, total = poll.get_results()
    return jsonify({'success': True, 'results': results, 'total': total})
