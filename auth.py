"""
Authentication Blueprint – Registration (OTP), Login, Logout
"""

import random
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, OTP
from utils import get_client_ip, get_device_info, log_audit

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validations
        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not phone or len(phone) < 10:
            errors.append('Valid phone number is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(phone=phone).first():
            errors.append('Phone number already registered.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html', username=username, phone=phone)

        # Store registration data in session, send OTP
        otp_code = str(random.randint(100000, 999999))
        otp = OTP(
            phone=phone,
            otp_code=otp_code,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(otp)
        db.session.commit()

        session['reg_username'] = username
        session['reg_phone'] = phone
        session['reg_password'] = password

        # Simulated OTP - in production, send via SMS gateway
        flash(f'Your OTP is: {otp_code} (This is a demo. In production, OTP will be sent via SMS.)', 'info')
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/register.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    phone = session.get('reg_phone')
    if not phone:
        flash('Please register first.', 'error')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        otp = OTP.query.filter_by(
            phone=phone,
            otp_code=entered_otp,
            is_used=False
        ).order_by(OTP.created_at.desc()).first()

        if otp and otp.is_valid():
            otp.is_used = True

            user = User(
                username=session['reg_username'],
                phone=phone,
                is_verified=True
            )
            user.set_password(session['reg_password'])
            db.session.add(user)
            db.session.commit()

            # Clear session
            session.pop('reg_username', None)
            session.pop('reg_phone', None)
            session.pop('reg_password', None)

            log_audit(user.id, 'user_registered', f'New user registered: {user.username}')
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')

    return render_template('auth/verify_otp.html', phone=phone)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(phone=phone).first()

        if user and user.check_password(password):
            if not user.is_verified:
                flash('Please verify your phone number first.', 'error')
                return render_template('auth/login.html', phone=phone)

            if user.is_banned:
                flash('Your account has been permanently banned.', 'error')
                return render_template('auth/login.html', phone=phone)

            if user.is_suspended:
                if user.suspension_until and datetime.utcnow() < user.suspension_until:
                    flash(f'Your account is suspended until {user.suspension_until.strftime("%d %b %Y")}.', 'error')
                    return render_template('auth/login.html', phone=phone)
                else:
                    user.is_suspended = False
                    user.suspension_until = None

            user.last_login = datetime.utcnow()
            user.last_ip = get_client_ip()
            user.last_device = get_device_info()
            db.session.commit()

            login_user(user, remember=True)
            log_audit(user.id, 'user_login', f'User logged in from {get_client_ip()}')

            # Redirect based on role
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role in ('admin', 'super_admin'):
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'reporter':
                return redirect(url_for('reporter.dashboard'))
            return redirect(url_for('public.index'))
        else:
            flash('Invalid phone number or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'user_logout', 'User logged out')
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('public.index'))
