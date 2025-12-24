from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Payment, Report
from datetime import datetime

operator_bp = Blueprint('operator', __name__, url_prefix='/operator')

@operator_bp.before_request
@login_required
def check_operator():
    # Проверка роли оператора
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Если используется атрибут role
    if hasattr(current_user, 'role'):
        if current_user.role not in ['operator', 'admin']:
            flash('Доступ запрещен. Требуются права оператора.', 'danger')
            return redirect(url_for('main.index'))
    # Или если используется is_operator
    elif hasattr(current_user, 'is_operator') and not current_user.is_operator:
        flash('Доступ запрещен. Требуются права оператора.', 'danger')
        return redirect(url_for('main.index'))

@operator_bp.route('/dashboard')
def dashboard():
    # Проверка прав
    if not (hasattr(current_user, 'is_operator') and current_user.is_operator or 
            hasattr(current_user, 'role') and current_user.role in ['operator', 'admin']):
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('main.index'))
    
    # Статистика для оператора
    user_stats = {
        'my_payments': Payment.query.filter_by(user_id=current_user.id).count(),
        'pending_my_payments': Payment.query.filter_by(
            user_id=current_user.id, status='pending'
        ).count(),
        'my_reports': Report.query.filter_by(created_by=current_user.id).count(),
    }
    
    return render_template('operator/dashboard.html', stats=user_stats)

@operator_bp.route('/my_payments')
def my_payments():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(
        Payment.date.desc()
    ).all()
    return render_template('operator/payments.html', payments=payments)

@operator_bp.route('/my_reports')
def my_reports():
    reports = Report.query.filter_by(created_by=current_user.id).order_by(
        Report.created_at.desc()
    ).all()
    return render_template('operator/reports.html', reports=reports)