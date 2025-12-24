from flask import Flask, redirect, render_template, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Building, Apartment, Resident, Service, Charge, Payment, Report
from models import ROLE_ADMIN, ROLE_OPERATOR, ROLE_RESIDENT
from admin import admin_bp
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zhkh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db.init_app(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Регистрация Blueprint
app.register_blueprint(admin_bp)

# Глобальный контекстный процессор
@app.context_processor
def inject_global_data():
    data = {
        'datetime': datetime,
        'now': datetime.utcnow(),
        'current_year': datetime.utcnow().year,
        'current_month': datetime.utcnow().month,
        'ROLE_ADMIN': ROLE_ADMIN,
        'ROLE_OPERATOR': ROLE_OPERATOR,
        'ROLE_RESIDENT': ROLE_RESIDENT,
    }
    
    # Добавляем проверки прав доступа
    if current_user.is_authenticated:
        data.update({
            'can_manage_users': current_user.has_permission('manage_users'),
            'can_manage_catalogs': current_user.has_permission('manage_catalogs'),
            'can_calculate_payments': current_user.has_permission('calculate_payments'),
            'can_manage_payments': current_user.has_permission('manage_payments'),
            'can_create_reports': current_user.has_permission('create_reports'),
            'can_access_personal': current_user.has_permission('personal_account'),
        })
    
    return data

# Простая страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.is_active:
                login_user(user, remember=True)
                flash(f'Добро пожаловать, {user.username}!', 'success')
                
                # Перенаправляем в зависимости от роли
                if user.is_admin:
                    return redirect('/admin/dashboard')
                elif user.is_operator:
                    return redirect('/operator/dashboard')
                else:
                    return redirect('/resident/dashboard')
            else:
                flash('Ваш аккаунт деактивирован.', 'danger')
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect('/login')

# Главная страница
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect('/admin/dashboard')
        elif current_user.is_operator:
            return redirect('/operator/dashboard')
        else:
            return redirect('/resident/dashboard')
    return redirect('/login')

# Дашборд оператора
@app.route('/operator/dashboard')
@login_required
def operator_dashboard():
    if not current_user.is_operator:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('operator/dashboard.html')

# Личный кабинет жильца
@app.route('/resident/dashboard')
@login_required
def resident_dashboard():
    if not current_user.is_resident:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('index'))
    
    # Получаем начисления и платежи для квартиры жильца
    charges = []
    payments = []
    
    if current_user.apartment_id:
        charges = Charge.query.filter_by(apartment_id=current_user.apartment_id)\
            .order_by(Charge.period.desc()).limit(10).all()
        payments = Payment.query.filter_by(apartment_id=current_user.apartment_id)\
            .order_by(Payment.date.desc()).limit(10).all()
    
    return render_template('resident/dashboard.html', 
                          charges=charges, 
                          payments=payments)

# Инициализация базы данных
def init_db():
    with app.app_context():
        # Удаляем старую базу если есть
        db_file = 'zhkh.db'
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                print(f'🗑️  Удалена старая база данных: {db_file}')
            except Exception as e:
                print(f'⚠️  Не удалось удалить базу данных: {e}')
        
        # Создаем таблицы
        db.create_all()
        print('✅ Созданы таблицы базы данных')
        
        # Создаем тестовых пользователей
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@example.com',
                'password': 'admin123',
                'role': ROLE_ADMIN,
                'full_name': 'Администратор Системы',
                'phone': '+7 (999) 000-00-01'
            },
            {
                'username': 'operator',
                'email': 'operator@example.com',
                'password': 'operator123',
                'role': ROLE_OPERATOR,
                'full_name': 'Оператор Управляющей Компании',
                'phone': '+7 (999) 000-00-02'
            },
            {
                'username': 'ivanov',
                'email': 'ivanov@example.com',
                'password': 'ivanov123',
                'role': ROLE_RESIDENT,
                'full_name': 'Иванов Иван Иванович',
                'phone': '+7 (999) 123-45-67'
            },
            {
                'username': 'petrov',
                'email': 'petrov@example.com',
                'password': 'petrov123',
                'role': ROLE_RESIDENT,
                'full_name': 'Петров Петр Петрович',
                'phone': '+7 (999) 765-43-21'
            }
        ]
        
        created_users = 0
        for user_data in users_data:
            if not User.query.filter_by(username=user_data['username']).first():
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    role=user_data['role'],
                    full_name=user_data['full_name'],
                    phone=user_data['phone'],
                    is_active=True
                )
                user.set_password(user_data['password'])
                db.session.add(user)
                created_users += 1
        
        if created_users > 0:
            print(f'👥 Создано {created_users} тестовых пользователей')
            print('   👑 Администратор: admin / admin123')
            print('   👷 Оператор УК: operator / operator123')
            print('   👤 Жилец 1: ivanov / ivanov123')
            print('   👤 Жилец 2: petrov / petrov123')
        try:
            db.session.commit()
            print('💾 Данные сохранены в базу данных')
            print('\n' + '='*50)
            print('🚀 Приложение готово к работе!')
            print('='*50)
            print('\n📋 Доступные пользователи:')
            print('   👑 Администратор: admin / admin123')
            print('   👷 Оператор УК: operator / operator123')
            print('   👤 Жилец 1: ivanov / ivanov123')
            print('   👤 Жилец 2: petrov / petrov123')
            print('='*50)
        except Exception as e:
            db.session.rollback()
            print(f'❌ Ошибка при сохранении данных: {e}')
            
# Создаем простые шаблоны если их нет
def create_default_templates():
    templates_dir = 'templates'
    admin_templates_dir = os.path.join(templates_dir, 'admin')
    
    # Создаем директории
    os.makedirs(admin_templates_dir, exist_ok=True)
    
    # Создаем простой base.html если его нет
    base_html = os.path.join(templates_dir, 'base.html')
    if not os.path.exists(base_html):
        with open(base_html, 'w', encoding='utf-8') as f:
            f.write('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}ЖКХ-Расчёт{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .navbar-brand {
            font-weight: bold;
        }
        .sidebar {
            min-height: 100vh;
            background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
            color: white;
        }
        .sidebar a {
            color: #ecf0f1;
            text-decoration: none;
            padding: 10px 15px;
            display: block;
        }
        .sidebar a:hover {
            background-color: #3498db;
            color: white;
        }
        .sidebar a.active {
            background-color: #2980b9;
        }
        .card {
            border: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 10px;
        }
        .stat-card {
            transition: transform 0.3s;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{{ url_for('index') }}">
                <i class="fas fa-building me-2"></i>ЖКХ-Расчёт
            </a>
            {% if current_user.is_authenticated %}
            <div class="navbar-nav ms-auto">
                <span class="navbar-text me-3">
                    <i class="fas fa-user me-1"></i>{{ current_user.username }}
                </span>
                <a class="btn btn-outline-light btn-sm" href="{{ url_for('logout') }}">
                    <i class="fas fa-sign-out-alt me-1"></i>Выйти
                </a>
            </div>
            {% endif %}
        </div>
    </nav>
    
    <div class="container-fluid">
        <div class="row">
            {% if current_user.is_authenticated %}
            <div class="col-md-2 p-0 sidebar">
                <div class="p-3">
                    <h5 class="text-center mb-4">Меню</h5>
                    <a href="{{ url_for('admin.dashboard') }}" class="mb-2 {% if request.endpoint == 'admin.dashboard' %}active{% endif %}">
                        <i class="fas fa-tachometer-alt me-2"></i>Панель управления
                    </a>
                    <a href="{{ url_for('admin.buildings') }}" class="mb-2 {% if 'buildings' in request.endpoint %}active{% endif %}">
                        <i class="fas fa-home me-2"></i>Дома
                    </a>
                    <a href="{{ url_for('admin.apartments') }}" class="mb-2 {% if 'apartments' in request.endpoint %}active{% endif %}">
                        <i class="fas fa-door-closed me-2"></i>Квартиры
                    </a>
                    <a href="{{ url_for('admin.residents') }}" class="mb-2 {% if 'residents' in request.endpoint %}active{% endif %}">
                        <i class="fas fa-users me-2"></i>Жильцы
                    </a>
                    <a href="{{ url_for('admin.services') }}" class="mb-2 {% if 'services' in request.endpoint and 'create' not in request.endpoint %}active{% endif %}">
                        <i class="fas fa-concierge-bell me-2"></i>Услуги
                    </a>
                    <a href="{{ url_for('admin.charges') }}" class="mb-2 {% if 'charges' in request.endpoint %}active{% endif %}">
                        <i class="fas fa-calculator me-2"></i>Начисления
                    </a>
                    <a href="{{ url_for('admin.payments') }}" class="mb-2 {% if 'payments' in request.endpoint and 'create' not in request.endpoint %}active{% endif %}">
                        <i class="fas fa-money-bill-wave me-2"></i>Платежи
                    </a>
                    <a href="{{ url_for('admin.reports') }}" class="mb-2 {% if 'reports' in request.endpoint and 'create' not in request.endpoint %}active{% endif %}">
                        <i class="fas fa-chart-bar me-2"></i>Отчеты
                    </a>
                </div>
            </div>
            <div class="col-md-10">
            {% else %}
            <div class="col-12">
            {% endif %}
                <div class="p-4">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show">
                                <i class="fas fa-{% if category == 'success' %}check-circle{% elif category == 'danger' %}exclamation-circle{% else %}info-circle{% endif %} me-2"></i>
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    {% block content %}{% endblock %}
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Автоматическое скрытие уведомлений через 5 секунд
        setTimeout(function() {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            });
        }, 5000);
    </script>
</body>
</html>
''')
        print('📄 Создан базовый шаблон')
    
    # Создаем простой dashboard.html если его нет
    dashboard_html = os.path.join(admin_templates_dir, 'dashboard.html')
    if not os.path.exists(dashboard_html):
        with open(dashboard_html, 'w', encoding='utf-8') as f:
            f.write('''
{% extends "base.html" %}

{% block title %}Панель управления{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="mb-0"><i class="fas fa-tachometer-alt me-2"></i>Панель управления</h1>
</div>

<div class="row mb-4">
    <div class="col-md-3 mb-3">
        <div class="card stat-card bg-primary text-white">
            <div class="card-body text-center">
                <i class="fas fa-home fa-3x mb-3"></i>
                <h2 class="card-title">{{ stats.buildings|default(0) }}</h2>
                <p class="card-text">Домов</p>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stat-card bg-success text-white">
            <div class="card-body text-center">
                <i class="fas fa-door-closed fa-3x mb-3"></i>
                <h2 class="card-title">{{ stats.apartments|default(0) }}</h2>
                <p class="card-text">Квартир</p>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stat-card bg-info text-white">
            <div class="card-body text-center">
                <i class="fas fa-users fa-3x mb-3"></i>
                <h2 class="card-title">{{ stats.residents|default(0) }}</h2>
                <p class="card-text">Жильцов</p>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stat-card bg-warning text-white">
            <div class="card-body text-center">
                <i class="fas fa-concierge-bell fa-3x mb-3"></i>
                <h2 class="card-title">{{ stats.services|default(0) }}</h2>
                <p class="card-text">Услуг</p>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-md-6 mb-4">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="fas fa-bolt me-2"></i>Быстрые действия</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="{{ url_for('admin.create_charge') }}" class="btn btn-primary">
                        <i class="fas fa-calculator me-2"></i>Создать начисления
                    </a>
                    <a href="{{ url_for('admin.create_payment') }}" class="btn btn-success">
                        <i class="fas fa-money-bill-wave me-2"></i>Добавить платеж
                    </a>
                    <a href="{{ url_for('admin.create_report') }}" class="btn btn-info text-white">
                        <i class="fas fa-file-alt me-2"></i>Создать отчет
                    </a>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-6 mb-4">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="fas fa-info-circle me-2"></i>Информация о системе</h5>
            </div>
            <div class="card-body">
                <p><i class="fas fa-database me-2"></i>База данных: SQLite</p>
                <p><i class="fas fa-calendar me-2"></i>Текущая дата: {{ now.strftime('%d.%m.%Y') }}</p>
                <p><i class="fas fa-user me-2"></i>Пользователь: {{ current_user.username }}</p>
                <p><i class="fas fa-shield-alt me-2"></i>Роль: {% if current_user.is_admin %}Администратор{% else %}Пользователь{% endif %}</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''')
        print('📄 Создан шаблон панели управления')

if __name__ == '__main__':
    # Создаем шаблоны если их нет
    create_default_templates()
    
    # Инициализация базы данных
    init_db()
    
    # Запуск приложения
    app.run(debug=True, port=5000)