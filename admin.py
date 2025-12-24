from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Building, Apartment, Resident, Service, Charge, Payment, Report
from datetime import datetime, date
from sqlalchemy import func, extract

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Контекстный процессор для статистики
@admin_bp.context_processor
def inject_stats():
    stats = {
        'buildings': Building.query.count(),
        'apartments': Apartment.query.count(),
        'residents': Resident.query.count(),
        'services': Service.query.filter_by(is_active=True).count(),
        'total_payments': db.session.query(func.sum(Payment.amount)).scalar() or 0,
        'pending_payments': Payment.query.filter_by(status='pending').count(),
        'total_charges': db.session.query(func.sum(Charge.total)).scalar() or 0,
    }
    return {'stats': stats}

@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin:
        flash('Доступ запрещен. Требуются права администратора.', 'danger')
        return redirect(url_for('index'))

# Главная панель
@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    return render_template('admin/dashboard.html')

# Управление домами
@admin_bp.route('/buildings')
def buildings():
    buildings_list = Building.query.all()
    return render_template('admin/buildings.html', buildings=buildings_list)

# Управление квартирами
@admin_bp.route('/apartments')
def apartments():
    apartments_list = Apartment.query.all()
    return render_template('admin/apartments.html', apartments=apartments_list)

# Управление жильцами
@admin_bp.route('/residents')
def residents():
    residents_list = Resident.query.all()
    return render_template('admin/residents.html', residents=residents_list)

# Управление услугами
@admin_bp.route('/services')
def services():
    services_list = Service.query.all()
    return render_template('admin/services.html', services=services_list)

# Создание услуги
@admin_bp.route('/service/create', methods=['GET', 'POST'])
def create_service():
    if request.method == 'POST':
        try:
            service = Service(
                name=request.form['name'],
                description=request.form.get('description'),
                unit=request.form.get('unit'),
                rate=float(request.form.get('rate', 0)),
                is_counter=bool(request.form.get('is_counter')),
                is_active=True
            )
            db.session.add(service)
            db.session.commit()
            flash('Услуга успешно создана', 'success')
            return redirect(url_for('admin.services'))
        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('admin/create_service.html')

# Управление начислениями
@admin_bp.route('/charges')
def charges():
    charges_list = Charge.query.order_by(Charge.period.desc()).all()
    return render_template('admin/charges.html', charges=charges_list)

# Создание начислений
@admin_bp.route('/charge/create', methods=['GET', 'POST'])
def create_charge():
    if request.method == 'POST':
        try:
            service_ids = request.form.getlist('service_ids')
            month = int(request.form['month'])
            year = int(request.form['year'])
            
            if not service_ids:
                flash('Выберите хотя бы одну услугу', 'danger')
                return redirect(url_for('admin.create_charge'))
            
            # Получаем выбранные услуги
            services = Service.query.filter(Service.id.in_(service_ids)).all()
            
            # Получаем квартиры
            apartment_filter = request.form.get('apartment_filter', 'all')
            
            if apartment_filter == 'building':
                building_id = request.form.get('building_id')
                if building_id:
                    apartments = Apartment.query.filter_by(building_id=building_id).all()
                else:
                    apartments = Apartment.query.all()
            else:
                apartments = Apartment.query.all()
            
            # Создаем начисления
            created_count = 0
            period_date = date(year, month, 1)
            
            for apartment in apartments:
                for service in services:
                    # Проверяем, не было ли уже начисления за этот период
                    existing_charge = Charge.query.filter_by(
                        apartment_id=apartment.id,
                        service_id=service.id,
                        period=period_date
                    ).first()
                    
                    if existing_charge:
                        continue  # Пропускаем, если начисление уже есть
                    
                    # Рассчитываем сумму начисления
                    if service.is_counter:
                        # Для услуг по счетчику - нужно вводить показания
                        amount = 0
                        total = 0
                    else:
                        # Для услуг по нормативу: тариф * площадь
                        amount = apartment.area
                        total = round(amount * service.rate, 2)
                    
                    charge = Charge(
                        apartment_id=apartment.id,
                        service_id=service.id,
                        period=period_date,
                        amount=amount,
                        total=total,
                        is_paid=False,
                        created_at=datetime.utcnow()
                    )
                    
                    db.session.add(charge)
                    created_count += 1
            
            db.session.commit()
            flash(f'Успешно создано {created_count} начислений за {month:02d}.{year}', 'success')
            return redirect(url_for('admin.charges'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании начислений: {str(e)}', 'danger')
    
    # GET запрос
    services_list = Service.query.filter_by(is_active=True).all()
    buildings = Building.query.all()
    
    return render_template('admin/create_charge.html', 
                          services=services_list,
                          buildings=buildings,
                          current_month=datetime.now().month,
                          current_year=datetime.now().year)

# Управление платежами
@admin_bp.route('/payments')
def payments():
    status_filter = request.args.get('status', 'all')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Payment.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Payment.date >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Payment.date <= date_to_obj)
        except ValueError:
            pass
    
    payments_list = query.order_by(Payment.date.desc()).all()
    
    return render_template('admin/payments.html', 
                          payments=payments_list,
                          status_filter=status_filter,
                          date_from=date_from,
                          date_to=date_to)

# Обновление платежа
@admin_bp.route('/payment/<int:payment_id>/update', methods=['POST'])
def update_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    
    try:
        payment.amount = float(request.form.get('amount', payment.amount))
        payment.status = request.form.get('status', payment.status)
        payment.payment_method = request.form.get('payment_method', payment.payment_method)
        payment.description = request.form.get('description', payment.description)
        
        db.session.commit()
        flash('Платеж успешно обновлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении платежа: {str(e)}', 'danger')
    
    return redirect(url_for('admin.payments'))

# Удаление платежа
@admin_bp.route('/payment/<int:payment_id>/delete', methods=['POST'])
def delete_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    
    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Платеж успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении платежа: {str(e)}', 'danger')
    
    return redirect(url_for('admin.payments'))

# Создание платежа
@admin_bp.route('/payment/create', methods=['GET', 'POST'])
def create_payment():
    if request.method == 'POST':
        try:
            payment = Payment(
                apartment_id=int(request.form['apartment_id']),
                amount=float(request.form['amount']),
                payment_method=request.form.get('payment_method', 'bank'),
                status=request.form.get('status', 'completed'),
                description=request.form.get('description', ''),
                date=datetime.utcnow()
            )
            
            db.session.add(payment)
            db.session.commit()
            flash('Платеж успешно создан', 'success')
            return redirect(url_for('admin.payments'))
        except Exception as e:
            flash(f'Ошибка при создании платежа: {str(e)}', 'danger')
    
    apartments = Apartment.query.all()
    return render_template('admin/create_payment.html', apartments=apartments)

# Управление отчетами
@admin_bp.route('/reports')
def reports():
    reports_list = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports_list)

# Создание отчета
@admin_bp.route('/report/create', methods=['GET', 'POST'])
def create_report():
    if request.method == 'POST':
        try:
            report = Report(
                title=request.form['title'],
                content=request.form['content'],
                report_type=request.form.get('report_type', 'general'),
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            
            if request.form.get('period'):
                try:
                    period_date = datetime.strptime(request.form['period'], '%Y-%m').date()
                    report.period = period_date
                except ValueError:
                    pass
            
            db.session.add(report)
            db.session.commit()
            flash('Отчет успешно создан', 'success')
            return redirect(url_for('admin.reports'))
        except Exception as e:
            flash(f'Ошибка при создании отчета: {str(e)}', 'danger')
    
    return render_template('admin/create_report.html')