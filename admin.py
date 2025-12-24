from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Payment, Report
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin:
        flash('Доступ запрещен. Требуются права администратора.', 'danger')
        return redirect(url_for('main.index'))

@admin_bp.route('/dashboard')
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'total_payments': Payment.query.count(),
        'total_reports': Report.query.count(),
        'pending_payments': Payment.query.filter_by(status='pending').count(),
        'completed_payments': Payment.query.filter_by(status='completed').count(),
    }
    return render_template('admin/dashboard.html', stats=stats)

@admin_bp.route('/users')
def users():
    users_list = User.query.all()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/payments')
def payments():
    payments_list = Payment.query.order_by(Payment.date.desc()).all()
    return render_template('admin/payments.html', payments=payments_list)

@admin_bp.route('/reports')
def reports():
    reports_list = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports_list)

@admin_bp.route('/payment/<int:id>/update', methods=['POST'])
def update_payment(id):
    payment = Payment.query.get_or_404(id)
    payment.status = request.form.get('status')
    payment.description = request.form.get('description')
    db.session.commit()
    flash('Платеж обновлен', 'success')
    return redirect(url_for('admin.payments'))

@admin_bp.route('/report/<int:id>/delete', methods=['POST'])
def delete_report(id):
    report = Report.query.get_or_404(id)
    db.session.delete(report)
    db.session.commit()
    flash('Отчет удален', 'success')
    return redirect(url_for('admin.reports'))