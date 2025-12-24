from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zhkh-secret-key-2024-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zhkh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.context_processor
def inject_datetime():
    return {'datetime': datetime}
def inject_now():
    return {'datetime': datetime, 'now': datetime.utcnow}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========== МОДЕЛИ БАЗЫ ДАННЫХ ==========

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='resident')  # admin, operator, resident
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Building(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    total_floors = db.Column(db.Integer, nullable=False)
    total_apartments = db.Column(db.Integer, nullable=False)
    year_built = db.Column(db.Integer)
    management_company = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Apartment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey('building.id'), nullable=False)
    apartment_number = db.Column(db.String(20), nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    area = db.Column(db.Float, nullable=False)
    rooms = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    building = db.relationship('Building', backref='apartments')

class Resident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    passport_number = db.Column(db.String(50))
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'))
    is_owner = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    apartment = db.relationship('Apartment', backref='residents')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(20))
    current_rate = db.Column(db.Float, nullable=False)
    is_counter_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    period = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0)
    meter_reading = db.Column(db.Float)
    calculated_amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, partially_paid, paid, overdue
    due_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    apartment = db.relationship('Apartment', backref='payments')
    service = db.relationship('Service', backref='payments')

class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='cash')
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    
    payment = db.relationship('Payment', backref='transactions')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== ДЕКОРАТОР ДЛЯ ПРОВЕРКИ АДМИНИСТРАТОРА ==========
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash('Требуются права администратора', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== МАРШРУТЫ АУТЕНТИФИКАЦИИ ==========

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('admin_dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========== АДМИНИСТРАТИВНЫЕ МАРШРУТЫ ==========

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_buildings = db.session.query(db.func.count(Building.id)).scalar() or 0
    total_apartments = db.session.query(db.func.count(Apartment.id)).scalar() or 0
    total_residents = db.session.query(db.func.count(Resident.id)).scalar() or 0
    total_services = db.session.query(db.func.count(Service.id)).scalar() or 0
    
    recent_buildings = Building.query.order_by(Building.created_at.desc()).limit(5).all()
    recent_residents = Resident.query.order_by(Resident.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_buildings=total_buildings,
                         total_apartments=total_apartments,
                         total_residents=total_residents,
                         total_services=total_services,
                         recent_buildings=recent_buildings,
                         recent_residents=recent_residents)

@app.route('/admin/buildings')
@login_required
@admin_required
def admin_buildings():
    buildings = Building.query.order_by(Building.address).all()
    return render_template('admin/buildings.html', buildings=buildings)

@app.route('/admin/apartments')
@login_required
@admin_required
def admin_apartments():
    apartments = Apartment.query.join(Building).order_by(Building.address, Apartment.apartment_number).all()
    buildings = Building.query.all()
    return render_template('admin/apartments.html', apartments=apartments, buildings=buildings)

@app.route('/admin/residents')
@login_required
@admin_required
def admin_residents():
    residents = Resident.query.join(Apartment).join(Building).order_by(Resident.full_name).all()
    apartments = Apartment.query.join(Building).order_by(Building.address, Apartment.apartment_number).all()
    return render_template('admin/residents.html', residents=residents, apartments=apartments)

@app.route('/admin/services')
@login_required
@admin_required
def admin_services():
    services = Service.query.order_by(Service.name).all()
    return render_template('admin/services.html', services=services)

@app.route('/admin/payments')
@login_required
@admin_required
def admin_payments():
    # Фильтры из GET-параметров
    status_filter = request.args.get('status', 'all')
    month_filter = request.args.get('month', datetime.now().strftime('%Y-%m'))
    building_filter = request.args.get('building', 'all')
    
    # Базовый запрос
    query = Payment.query.join(Apartment).join(Building).join(Service)
    
    # Применяем фильтры
    if status_filter != 'all':
        query = query.filter(Payment.status == status_filter)
    
    if building_filter != 'all':
        query = query.filter(Building.id == int(building_filter))
    
    # Фильтр по месяцу
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            query = query.filter(db.extract('year', Payment.period) == year,
                               db.extract('month', Payment.period) == month)
        except:
            pass
    
    payments = query.order_by(Payment.due_date).all()
    buildings = Building.query.all()
    
    # Статистика
    total_amount = sum(p.amount for p in payments)
    total_paid = sum(p.paid_amount for p in payments)
    total_due = total_amount - total_paid
    
    # Группировка по статусам
    status_stats = {
        'pending': len([p for p in payments if p.status == 'pending']),
        'partially_paid': len([p for p in payments if p.status == 'partially_paid']),
        'paid': len([p for p in payments if p.status == 'paid']),
        'overdue': len([p for p in payments if p.status == 'overdue'])
    }
    
    return render_template('admin/payments.html',
                         payments=payments,
                         buildings=buildings,
                         status_filter=status_filter,
                         month_filter=month_filter,
                         building_filter=building_filter,
                         total_amount=total_amount,
                         total_paid=total_paid,
                         total_due=total_due,
                         status_stats=status_stats)

@app.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    buildings = Building.query.all()
    services = Service.query.all()
    
    current_month = datetime.now().strftime('%Y-%m')
    
    return render_template('admin/reports.html',
                         buildings=buildings,
                         services=services,
                         current_month=current_month)

# ========== CRUD ОПЕРАЦИИ ДЛЯ ДОМОВ ==========

@app.route('/admin/buildings/add', methods=['POST'])
@login_required
@admin_required
def add_building():
    try:
        building = Building(
            address=request.form.get('address'),
            total_floors=int(request.form.get('total_floors', 1)),
            total_apartments=int(request.form.get('total_apartments', 1)),
            year_built=int(request.form.get('year_built')) if request.form.get('year_built') else None,
            management_company=request.form.get('management_company', '')
        )
        db.session.add(building)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Дом добавлен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/buildings/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_building(id):
    building = Building.query.get_or_404(id)
    try:
        building.address = request.form.get('address')
        building.total_floors = int(request.form.get('total_floors', 1))
        building.total_apartments = int(request.form.get('total_apartments', 1))
        building.year_built = int(request.form.get('year_built')) if request.form.get('year_built') else None
        building.management_company = request.form.get('management_company', '')
        db.session.commit()
        return jsonify({'success': True, 'message': 'Дом обновлен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/buildings/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_building(id):
    building = Building.query.get_or_404(id)
    try:
        db.session.delete(building)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Дом удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# ========== CRUD ОПЕРАЦИИ ДЛЯ КВАРТИР ==========

@app.route('/admin/apartments/add', methods=['POST'])
@login_required
@admin_required
def add_apartment():
    try:
        apartment = Apartment(
            building_id=int(request.form.get('building_id')),
            apartment_number=request.form.get('apartment_number'),
            floor=int(request.form.get('floor', 1)),
            area=float(request.form.get('area', 0)),
            rooms=int(request.form.get('rooms', 1))
        )
        db.session.add(apartment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Квартира добавлена'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/apartments/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_apartment(id):
    apartment = Apartment.query.get_or_404(id)
    try:
        db.session.delete(apartment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Квартира удалена'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# ========== CRUD ОПЕРАЦИИ ДЛЯ ЖИЛЬЦОВ ==========

@app.route('/admin/residents/add', methods=['POST'])
@login_required
@admin_required
def add_resident():
    try:
        apartment_id = request.form.get('apartment_id')
        resident = Resident(
            full_name=request.form.get('full_name'),
            phone=request.form.get('phone', ''),
            email=request.form.get('email', ''),
            passport_number=request.form.get('passport_number', ''),
            apartment_id=int(apartment_id) if apartment_id and apartment_id != 'null' else None,
            is_owner=bool(request.form.get('is_owner'))
        )
        db.session.add(resident)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Жилец добавлен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/residents/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_resident(id):
    resident = Resident.query.get_or_404(id)
    try:
        db.session.delete(resident)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Жилец удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# ========== CRUD ОПЕРАЦИИ ДЛЯ УСЛУГ ==========

@app.route('/admin/services/add', methods=['POST'])
@login_required
@admin_required
def add_service():
    try:
        service = Service(
            name=request.form.get('name'),
            description=request.form.get('description', ''),
            unit=request.form.get('unit', ''),
            current_rate=float(request.form.get('current_rate', 0)),
            is_counter_required=bool(request.form.get('is_counter_required'))
        )
        db.session.add(service)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Услуга добавлена'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/services/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(id):
    service = Service.query.get_or_404(id)
    try:
        db.session.delete(service)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Услуга удалена'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# ========== ОПЕРАЦИИ ДЛЯ ПЛАТЕЖЕЙ ==========

@app.route('/admin/payments/add', methods=['POST'])
@login_required
@admin_required
def add_payment():
    try:
        apartment_id = request.form.get('apartment_id')
        service_id = request.form.get('service_id')
        period_str = request.form.get('period')
        amount = float(request.form.get('amount', 0))
        meter_reading = request.form.get('meter_reading')
        due_date_str = request.form.get('due_date')
        
        # Парсим даты
        period = datetime.strptime(period_str, '%Y-%m').date()
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        
        payment = Payment(
            apartment_id=int(apartment_id),
            service_id=int(service_id),
            period=period,
            amount=amount,
            meter_reading=float(meter_reading) if meter_reading else None,
            calculated_amount=amount,
            due_date=due_date,
            status='pending'
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Платеж добавлен', 'id': payment.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/payments/<int:id>/add_payment', methods=['POST'])
@login_required
@admin_required
def add_payment_transaction(id):
    try:
        payment = Payment.query.get_or_404(id)
        amount = float(request.form.get('amount', 0))
        payment_method = request.form.get('payment_method', 'cash')
        description = request.form.get('description', '')
        
        # Создаем транзакцию
        transaction = PaymentTransaction(
            payment_id=payment.id,
            amount=amount,
            payment_method=payment_method,
            description=description,
            created_by=current_user.username
        )
        
        # Обновляем статус платежа
        payment.paid_amount += amount
        payment.payment_date = datetime.utcnow().date()
        
        if payment.paid_amount >= payment.amount:
            payment.status = 'paid'
        elif payment.paid_amount > 0:
            payment.status = 'partially_paid'
        
        # Проверка просрочки
        if payment.due_date < datetime.utcnow().date() and payment.status != 'paid':
            payment.status = 'overdue'
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Оплата зачислена'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/payments/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_payment(id):
    try:
        payment = Payment.query.get_or_404(id)
        db.session.delete(payment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Платеж удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/payments/generate', methods=['POST'])
@login_required
@admin_required
def generate_payments():
    try:
        month = request.form.get('month')
        building_id = request.form.get('building_id')
        
        # Получаем все квартиры в доме
        apartments = Apartment.query
        if building_id != 'all':
            apartments = apartments.filter_by(building_id=int(building_id))
        apartments = apartments.all()
        
        # Получаем все услуги
        services = Service.query.all()
        
        generated_count = 0
        
        for apartment in apartments:
            for service in services:
                # Проверяем, не существует ли уже такой платеж
                existing = Payment.query.filter_by(
                    apartment_id=apartment.id,
                    service_id=service.id,
                    period=datetime.strptime(month, '%Y-%m').date()
                ).first()
                
                if not existing:
                    # Рассчитываем сумму (базовая логика)
                    amount = apartment.area * service.current_rate
                    
                    payment = Payment(
                        apartment_id=apartment.id,
                        service_id=service.id,
                        period=datetime.strptime(month, '%Y-%m').date(),
                        amount=amount,
                        calculated_amount=amount,
                        due_date=datetime.strptime(month + '-25', '%Y-%m-%d').date(),
                        status='pending'
                    )
                    
                    db.session.add(payment)
                    generated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Сгенерировано {generated_count} платежей'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# ========== API ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ ==========

@app.route('/api/buildings')
@login_required
def api_buildings():
    buildings = Building.query.all()
    result = [{
        'id': b.id,
        'address': b.address,
        'total_floors': b.total_floors,
        'total_apartments': b.total_apartments
    } for b in buildings]
    return jsonify(result)

@app.route('/api/apartments/<int:building_id>')
@login_required
def api_apartments_by_building(building_id):
    apartments = Apartment.query.filter_by(building_id=building_id).all()
    result = [{
        'id': a.id,
        'number': a.apartment_number,
        'floor': a.floor,
        'area': a.area,
        'building_address': a.building.address
    } for a in apartments]
    return jsonify(result)

@app.route('/api/apartments')
@login_required
def api_all_apartments():
    apartments = Apartment.query.join(Building).all()
    result = [{
        'id': a.id,
        'number': a.apartment_number,
        'building': a.building.address,
        'building_id': a.building_id
    } for a in apartments]
    return jsonify(result)

@app.route('/api/services')
@login_required
def api_services():
    services = Service.query.all()
    result = [{
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'unit': s.unit,
        'current_rate': s.current_rate,
        'is_counter_required': s.is_counter_required
    } for s in services]
    return jsonify(result)

@app.route('/api/statistics')
@login_required
def api_statistics():
    stats = {
        'total_buildings': db.session.query(db.func.count(Building.id)).scalar() or 0,
        'total_apartments': db.session.query(db.func.count(Apartment.id)).scalar() or 0,
        'total_residents': db.session.query(db.func.count(Resident.id)).scalar() or 0,
        'total_services': db.session.query(db.func.count(Service.id)).scalar() or 0,
        'total_payments': db.session.query(db.func.count(Payment.id)).scalar() or 0,
        'total_payments_amount': db.session.query(db.func.sum(Payment.amount)).scalar() or 0,
        'total_paid_amount': db.session.query(db.func.sum(Payment.paid_amount)).scalar() or 0
    }
    return jsonify(stats)

@app.route('/api/reports/financial')
@login_required
@admin_required
def api_financial_report():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        building_id = request.args.get('building_id')
        
        # Базовый запрос
        query = Payment.query.join(Apartment).join(Building)
        
        if start_date:
            query = query.filter(Payment.period >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Payment.period <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if building_id and building_id != 'all':
            query = query.filter(Building.id == int(building_id))
        
        payments = query.all()
        
        # Формируем отчет
        report = {
            'total_charged': sum(p.amount for p in payments) or 0,
            'total_paid': sum(p.paid_amount for p in payments) or 0,
            'total_due': sum(p.amount - p.paid_amount for p in payments) or 0,
            'payments_by_status': {
                'pending': len([p for p in payments if p.status == 'pending']),
                'partially_paid': len([p for p in payments if p.status == 'partially_paid']),
                'paid': len([p for p in payments if p.status == 'paid']),
                'overdue': len([p for p in payments if p.status == 'overdue'])
            },
            'payments_by_service': [],
            'payments_by_month': []
        }
        
        # По услугам
        services = Service.query.all()
        for service in services:
            service_payments = [p for p in payments if p.service_id == service.id]
            report['payments_by_service'].append({
                'service_name': service.name,
                'amount': sum(p.amount for p in service_payments) or 0,
                'paid': sum(p.paid_amount for p in service_payments) or 0
            })
        
        # По месяцам
        months = {}
        for payment in payments:
            month_key = payment.period.strftime('%Y-%m')
            if month_key not in months:
                months[month_key] = {'charged': 0, 'paid': 0}
            months[month_key]['charged'] += payment.amount
            months[month_key]['paid'] += payment.paid_amount
        
        for month, data in sorted(months.items()):
            report['payments_by_month'].append({
                'month': month,
                'charged': data['charged'],
                'paid': data['paid']
            })
        
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/reports/debtors')
@login_required
@admin_required
def api_debtors_report():
    try:
        building_id = request.args.get('building_id')
        min_debt = float(request.args.get('min_debt', 0))
        
        # Получаем платежи с задолженностью
        query = Payment.query.join(Apartment).join(Building)
        if building_id and building_id != 'all':
            query = query.filter(Building.id == int(building_id))
        
        payments = query.filter(Payment.paid_amount < Payment.amount).all()
        
        # Группируем по квартирам
        debtors_dict = {}
        for payment in payments:
            apartment = payment.apartment
            debt = payment.amount - payment.paid_amount
            
            if debt < min_debt:
                continue
            
            key = apartment.id
            if key not in debtors_dict:
                debtors_dict[key] = {
                    'address': f"{apartment.building.address}, кв. {apartment.apartment_number}",
                    'total_debt': 0,
                    'services': [],
                    'residents': [r.full_name for r in apartment.residents]
                }
            
            debtors_dict[key]['total_debt'] += debt
            debtors_dict[key]['services'].append({
                'service': payment.service.name,
                'debt': debt,
                'period': payment.period.strftime('%Y-%m'),
                'due_date': payment.due_date.strftime('%d.%m.%Y')
            })
        
        # Конвертируем в список и сортируем
        debtors_list = list(debtors_dict.values())
        debtors_list.sort(key=lambda x: x['total_debt'], reverse=True)
        
        return jsonify({
            'total_debtors': len(debtors_list),
            'total_debt_amount': sum(d['total_debt'] for d in debtors_list),
            'debtors': debtors_list[:50]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/reports/export/<report_type>')
@login_required
@admin_required
def export_report(report_type):
    try:
        if report_type == 'financial':
            data = api_financial_report().get_json()
            return jsonify({'success': True, 'message': 'Отчет готов к экспорту', 'data': data})
        elif report_type == 'debtors':
            data = api_debtors_report().get_json()
            return jsonify({'success': True, 'message': 'Отчет готов к экспорту', 'data': data})
        else:
            return jsonify({'error': 'Неизвестный тип отчета'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Создаем администратора по умолчанию
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@zhkh.ru', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('=' * 50)
            print('Создан администратор:')
            print('Логин: admin')
            print('Пароль: admin123')
            print('=' * 50)
        print('База данных инициализирована')
        print('Сервер запущен: http://localhost:5000')
    
    app.run(debug=True, host='0.0.0.0', port=5000)