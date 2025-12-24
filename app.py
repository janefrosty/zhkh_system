# app.py
from flask import Flask, redirect, render_template, request, flash, url_for, Blueprint, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os

# Импортируем расширения
from extensions import db, login_manager

# Создание приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zhkh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений с приложением
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Импорт моделей должен быть после инициализации db
with app.app_context():
    from models import User, Payment, Report, House, Receipt, Task

# Контекстный процессор для передачи datetime в шаблоны
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Маршрут для загрузки пользователя
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Основные маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            
            # Перенаправляем в зависимости от роли
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif user.is_operator:
                return redirect(url_for('operator.operator_dashboard'))
            else:
                return redirect(url_for('user.dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# ============ USER BLUEPRINT (для обычных пользователей) ============
user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
@login_required
def dashboard():
    # Статистика для обычного пользователя
    user_houses = House.query.filter_by(user_id=current_user.id).all()
    user_receipts = Receipt.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'my_payments': Payment.query.filter_by(user_id=current_user.id).count(),
        'pending_payments': Payment.query.filter_by(user_id=current_user.id, status='pending').count(),
        'completed_payments': Payment.query.filter_by(user_id=current_user.id, status='completed').count(),
        'total_debt': sum(r.amount for r in user_receipts if not r.is_paid),
        'houses_count': len(user_houses),
        'unpaid_receipts': sum(1 for r in user_receipts if not r.is_paid),
    }
    
    # Последние платежи
    recent_payments = Payment.query.filter_by(user_id=current_user.id).order_by(
        Payment.date.desc()
    ).limit(5).all()
    
    # Последние квитанции
    recent_receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(
        Receipt.created_at.desc()
    ).limit(5).all()
    
    return render_template('user/dashboard.html', 
                          stats=stats, 
                          recent_payments=recent_payments,
                          recent_receipts=recent_receipts)

@user_bp.route('/payments')
@login_required
def my_payments():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(
        Payment.date.desc()
    ).all()
    return render_template('user/payments.html', payments=payments)

@user_bp.route('/receipts')
@login_required
def my_receipts():
    receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(
        Receipt.created_at.desc()
    ).all()
    return render_template('user/receipts.html', receipts=receipts)

@user_bp.route('/receipt/<int:receipt_id>/pay', methods=['POST'])
@login_required
def pay_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    
    if receipt.user_id != current_user.id:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('user.my_receipts'))
    
    # Создаем платеж
    payment = Payment(
        user_id=current_user.id,
        amount=receipt.amount,
        status='completed',
        description=f'Оплата квитанции #{receipt.id}'
    )
    db.session.add(payment)
    
    # Помечаем квитанцию как оплаченную
    receipt.is_paid = True
    receipt.paid_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Квитанция #{receipt.id} успешно оплачена!', 'success')
    return redirect(url_for('user.my_receipts'))

@user_bp.route('/houses')
@login_required
def my_houses():
    houses = House.query.filter_by(user_id=current_user.id).all()
    return render_template('user/houses.html', houses=houses)

@user_bp.route('/profile')
@login_required
def profile():
    return render_template('user/profile.html', user=current_user)

# ============ ADMIN BLUEPRINT ============
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    # Получаем статистику
    today = datetime.utcnow().date()
    month_ago = today - timedelta(days=30)
    
    stats = {
        'total_users': User.query.count(),
        'total_payments': Payment.query.count(),
        'total_reports': Report.query.count(),
        'total_houses': House.query.count(),
        'pending_payments': Payment.query.filter_by(status='pending').count(),
        'completed_payments': Payment.query.filter_by(status='completed').count(),
        'total_amount': sum(p.amount for p in Payment.query.filter_by(status='completed').all()),
        'overdue_receipts': Receipt.query.filter(Receipt.due_date < today, Receipt.is_paid == False).count(),
        'recent_payments_count': Payment.query.filter(Payment.date >= month_ago).count(),
    }
    
    # Последние пользователи
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Последние платежи
    recent_payments = Payment.query.order_by(Payment.date.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                          stats=stats, 
                          recent_users=recent_users,
                          recent_payments=recent_payments)

@admin_bp.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    users_list = User.query.all()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        if request.form.get('password'):
            user.set_password(request.form.get('password'))
        
        db.session.commit()
        flash('Пользователь обновлен', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/payments')
@login_required
def admin_payments():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    payments_list = Payment.query.order_by(Payment.date.desc()).all()
    return render_template('admin/payments.html', payments=payments_list)

@admin_bp.route('/reports')
@login_required
def admin_reports():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    reports_list = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports_list)

@admin_bp.route('/report/create', methods=['GET', 'POST'])
@login_required
def create_report():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        report_type = request.form.get('report_type')
        
        report = Report(
            title=title,
            content=content,
            report_type=report_type,
            created_by=current_user.id
        )
        db.session.add(report)
        db.session.commit()
        
        flash('Отчет создан', 'success')
        return redirect(url_for('admin.admin_reports'))
    
    return render_template('admin/create_report.html')

@admin_bp.route('/houses')
@login_required
def admin_houses():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    houses_list = House.query.all()
    return render_template('admin/houses.html', houses=houses_list)

@admin_bp.route('/house/create', methods=['GET', 'POST'])
@login_required
def create_house():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.filter_by(role='user').all()
    
    if request.method == 'POST':
        address = request.form.get('address')
        area = request.form.get('area')
        user_id = request.form.get('user_id')
        
        house = House(
            address=address,
            area=float(area),
            user_id=user_id
        )
        db.session.add(house)
        db.session.commit()
        
        flash('Дом добавлен', 'success')
        return redirect(url_for('admin.admin_houses'))
    
    return render_template('admin/create_house.html', users=users)

@admin_bp.route('/settings')
@login_required
def settings():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    return render_template('admin/settings.html')

@admin_bp.route('/receipts')
@login_required
def admin_receipts():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    receipts = Receipt.query.order_by(Receipt.created_at.desc()).all()
    return render_template('admin/receipts.html', receipts=receipts)

@admin_bp.route('/receipt/create', methods=['GET', 'POST'])
@login_required
def create_receipt():
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.all()
    houses = House.query.all()
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        house_id = request.form.get('house_id')
        amount = request.form.get('amount')
        description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        
        receipt = Receipt(
            user_id=user_id,
            house_id=house_id,
            amount=float(amount),
            description=description,
            due_date=due_date
        )
        db.session.add(receipt)
        db.session.commit()
        
        flash('Квитанция создана', 'success')
        return redirect(url_for('admin.admin_receipts'))
    
    return render_template('admin/create_receipt.html', users=users, houses=houses)

# ============ OPERATOR BLUEPRINT ============
operator_bp = Blueprint('operator', __name__, url_prefix='/operator')

@operator_bp.route('/dashboard')
@login_required
def operator_dashboard():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    # Статистика для оператора
    today = datetime.utcnow().date()
    
    stats = {
        'total_users': User.query.filter_by(role='user').count(),
        'overdue_payments': Receipt.query.filter(Receipt.due_date < today, Receipt.is_paid == False).count(),
        'pending_tasks': Task.query.filter_by(status='pending').count(),
        'completed_tasks': Task.query.filter_by(status='completed').count(),
    }
    
    # Пользователи с просроченными платежами
    overdue_users = User.query.join(Receipt).filter(
        Receipt.due_date < today, 
        Receipt.is_paid == False,
        User.role == 'user'
    ).distinct().limit(5).all()
    
    # Последние задачи
    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
    
    return render_template('operator/dashboard.html', 
                          stats=stats, 
                          overdue_users=overdue_users,
                          recent_tasks=recent_tasks)

@operator_bp.route('/users')
@login_required
def operator_users():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    users_list = User.query.filter_by(role='user').all()
    return render_template('operator/users.html', users=users_list)

@operator_bp.route('/user/<int:user_id>/details')
@login_required
def user_details(user_id):
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    houses = House.query.filter_by(user_id=user_id).all()
    payments = Payment.query.filter_by(user_id=user_id).order_by(Payment.date.desc()).limit(10).all()
    receipts = Receipt.query.filter_by(user_id=user_id).order_by(Receipt.created_at.desc()).all()
    
    # Статистика пользователя
    user_stats = {
        'total_payments': len(payments),
        'total_receipts': len(receipts),
        'unpaid_receipts': sum(1 for r in receipts if not r.is_paid),
        'total_debt': sum(r.amount for r in receipts if not r.is_paid),
    }
    
    return render_template('operator/user_details.html', 
                          user=user, 
                          houses=houses, 
                          payments=payments, 
                          receipts=receipts,
                          stats=user_stats)

@operator_bp.route('/overdue')
@login_required
def overdue_payments():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    today = datetime.utcnow().date()
    overdue_receipts = Receipt.query.filter(
        Receipt.due_date < today, 
        Receipt.is_paid == False
    ).order_by(Receipt.due_date).all()
    
    return render_template('operator/overdue.html', overdue_receipts=overdue_receipts)

@operator_bp.route('/tasks')
@login_required
def tasks():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    tasks_list = Task.query.order_by(Task.priority.desc(), Task.created_at.desc()).all()
    return render_template('operator/tasks.html', tasks=tasks_list)

@operator_bp.route('/task/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        
        task = Task(
            title=title,
            description=description,
            priority=priority,
            assigned_to=current_user.id,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()
        
        flash('Задача создана', 'success')
        return redirect(url_for('operator.tasks'))
    
    return render_template('operator/create_task.html')

@operator_bp.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    task = Task.query.get_or_404(task_id)
    task.status = 'completed'
    task.completed_at = datetime.utcnow()
    
    db.session.commit()
    flash('Задача отмечена как выполненная', 'success')
    return redirect(url_for('operator.tasks'))

@operator_bp.route('/payments')
@login_required
def operator_payments():
    if not current_user.is_operator:
        flash('Требуются права оператора', 'danger')
        return redirect(url_for('index'))
    
    payments_list = Payment.query.order_by(Payment.date.desc()).all()
    return render_template('operator/payments.html', payments=payments_list)


@admin_bp.route('/report/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report(report_id):  # Исправлено имя функции
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    
    flash('Отчет удален', 'success')
    return redirect(url_for('admin.admin_reports'))

@admin_bp.route('/payment/<int:payment_id>/update', methods=['POST'])
@login_required
def update_payment(payment_id):
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    payment = Payment.query.get_or_404(payment_id)
    payment.status = request.form.get('status')
    payment.description = request.form.get('description')
    
    db.session.commit()
    flash('Платеж обновлен', 'success')
    return redirect(url_for('admin.admin_payments'))

@admin_bp.route('/house/<int:house_id>/delete', methods=['POST'])
@login_required
def delete_house(house_id):
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    house = House.query.get_or_404(house_id)
    db.session.delete(house)
    db.session.commit()
    
    flash('Дом удален', 'success')
    return redirect(url_for('admin.admin_houses'))

@admin_bp.route('/receipt/<int:receipt_id>/delete', methods=['POST'])
@login_required
def delete_receipt(receipt_id):
    if not current_user.is_admin:
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('index'))
    
    receipt = Receipt.query.get_or_404(receipt_id)
    db.session.delete(receipt)
    db.session.commit()
    
    flash('Квитанция удалена', 'success')
    return redirect(url_for('admin.admin_receipts'))

# Регистрация blueprints
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(operator_bp)

# Инициализация базы данных
def init_db():
    with app.app_context():
        # Создаем все таблицы
        db.create_all()
        
        print("Создание таблиц завершено")
        
        # Проверяем и создаем тестовые данные
        # Создаем администратора, оператора и пользователей
        roles = [
            ('admin', 'admin123', 'admin', 'admin@example.com'),
            ('operator', 'operator123', 'operator', 'operator@example.com'),
            ('user', 'user123', 'user', 'user@example.com'),
            ('user1', 'user123', 'user', 'user1@example.com'),
            ('user2', 'user123', 'user', 'user2@example.com'),
            ('user3', 'user123', 'user', 'user3@example.com'),
        ]
        
        for username, password, role, email in roles:
            if not User.query.filter_by(username=username).first():
                user = User(
                    username=username,
                    email=email,
                    role=role
                )
                user.set_password(password)
                db.session.add(user)
                print(f"Создан {role}: {username} / {password}")
        
        db.session.commit()
        
        # Создаем тестовые дома
        if House.query.count() == 0:
            users = User.query.filter_by(role='user').all()
            addresses = [
                'ул. Ленина, д. 10, кв. 25',
                'ул. Пушкина, д. 5, кв. 12',
                'пр. Мира, д. 15, кв. 8',
                'ул. Советская, д. 22, кв. 17',
                'ул. Гагарина, д. 7, кв. 31'
            ]
            
            for i, address in enumerate(addresses):
                house = House(
                    address=address,
                    area=50.0 + (i * 10),
                    user_id=users[i % len(users)].id if users else 3
                )
                db.session.add(house)
            
            print("Созданы тестовые дома")
        
        # Создаем тестовые квитанции
        if Receipt.query.count() == 0:
            today = datetime.utcnow()
            users = User.query.filter_by(role='user').all()
            houses = House.query.all()
            
            for i in range(10):
                user = users[i % len(users)] if users else User.query.get(3)
                house = houses[i % len(houses)] if houses else None
                
                receipt = Receipt(
                    user_id=user.id,
                    house_id=house.id if house else None,
                    amount=1000.0 + (i * 500),
                    description=f'Квитанция за коммунальные услуги #{i+1}',
                    is_paid=i % 3 != 0,  # Каждая третья не оплачена
                    due_date=today + timedelta(days=(i-5)*7)  # Некоторые просрочены
                )
                db.session.add(receipt)
            
            print("Созданы тестовые квитанции")
        
        # Создаем тестовые платежи
        if Payment.query.count() == 0:
            users = User.query.filter_by(role='user').all()
            
            for i in range(15):
                user = users[i % len(users)] if users else User.query.get(3)
                
                payment = Payment(
                    user_id=user.id,
                    amount=800.0 + (i * 300),
                    status='completed' if i % 5 != 0 else 'pending',
                    description=f'Платеж за услуги #{i+1}',
                    date=today - timedelta(days=i*2)
                )
                db.session.add(payment)
            
            print("Созданы тестовые платежи")
        
        # Создаем тестовые задачи
        if Task.query.count() == 0:
            operator = User.query.filter_by(role='operator').first()
            
            tasks_data = [
                ('Позвонить пользователю user1', 'Напоминание о просроченном платеже', 'high'),
                ('Проверить показания счетчиков', 'Обход домов №1-5', 'medium'),
                ('Подготовить отчет по долгам', 'За январь 2024', 'low'),
                ('Обработать жалобу', 'Протечка в подъезде 2', 'high'),
            ]
            
            for title, description, priority in tasks_data:
                task = Task(
                    title=title,
                    description=description,
                    priority=priority,
                    assigned_to=operator.id if operator else 2,
                    status='pending' if priority == 'high' else 'completed'
                )
                db.session.add(task)
            
            print("Созданы тестовые задачи")
        
        # Создаем тестовые отчеты
        if Report.query.count() == 0:
            admin = User.query.filter_by(role='admin').first()
            
            reports = [
                ('Финансовый отчет за январь', 'Поступления: 150,000 руб. Расходы: 120,000 руб.', 'financial'),
                ('Технический отчет', 'Ремонтные работы завершены в 3 домах', 'technical'),
                ('Анализ жалоб', 'Основные проблемы: лифты, крыши, водоснабжение', 'analysis'),
            ]
            
            for title, content, report_type in reports:
                report = Report(
                    title=title,
                    content=content,
                    report_type=report_type,
                    created_by=admin.id if admin else 1
                )
                db.session.add(report)
            
            print("Созданы тестовые отчеты")
        
        try:
            db.session.commit()
            print("База данных успешно инициализирована")
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при инициализации БД: {e}")

@app.context_processor
def inject_now():
    return {
        'datetime': datetime,
        'now': datetime.utcnow()
    }

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)