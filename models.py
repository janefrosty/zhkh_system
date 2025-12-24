from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

ROLE_ADMIN = 'admin'
ROLE_OPERATOR = 'operator'
ROLE_RESIDENT = 'resident'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default=ROLE_RESIDENT)  # Изменяем is_admin на role
    is_active = db.Column(db.Boolean, default=True)
    full_name = db.Column(db.String(150))  # Полное имя
    phone = db.Column(db.String(20))  # Телефон
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'))  # Для жильцов
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    apartment = db.relationship('Apartment', backref='users', lazy=True)  # Для жильцов
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # Проверки ролей
    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN
    
    @property
    def is_operator(self):
        return self.role == ROLE_OPERATOR
    
    @property
    def is_resident(self):
        return self.role == ROLE_RESIDENT
    
    def has_permission(self, permission):
        permissions = {
            # Администратор - все права
            ROLE_ADMIN: {
                'manage_users': True,
                'system_settings': True,
                'manage_catalogs': True,
                'calculate_payments': True,
                'manage_payments': True,
                'create_reports': True,
                'personal_account': True,
            },
            # Оператор УК
            ROLE_OPERATOR: {
                'manage_users': False,
                'system_settings': False,
                'manage_catalogs': True,  # W - редактирование
                'calculate_payments': True,  # W - редактирование
                'manage_payments': True,  # W - редактирование
                'create_reports': True,  # W - редактирование
                'personal_account': False,
            },
            # Жилец
            ROLE_RESIDENT: {
                'manage_users': False,
                'system_settings': False,
                'manage_catalogs': False,
                'calculate_payments': True,  # R - чтение
                'manage_payments': True,  # R - чтение
                'create_reports': True,  # R - чтение
                'personal_account': True,  # W - редактирование
            }
        }
        return permissions.get(self.role, {}).get(permission, False)
    
    # Flask-Link методы
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

class Building(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    floors = db.Column(db.Integer, default=5)
    apartments_count = db.Column(db.Integer, default=20)
    year_built = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    apartments = db.relationship('Apartment', backref='building', lazy=True, cascade='all, delete-orphan')

class Apartment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False)
    area = db.Column(db.Float, default=50.0)
    rooms = db.Column(db.Integer, default=2)
    floor = db.Column(db.Integer)
    building_id = db.Column(db.Integer, db.ForeignKey('building.id'), nullable=False)
    
    residents = db.relationship('Resident', backref='apartment', lazy=True, cascade='all, delete-orphan')
    charges = db.relationship('Charge', backref='apartment', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='apartment', lazy=True, cascade='all, delete-orphan')

class Resident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    is_owner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(20))  # м³, кВт·ч, м² и т.д.
    rate = db.Column(db.Float, default=0.0)  # Тариф за единицу
    is_counter = db.Column(db.Boolean, default=False)  # Счетчик
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    charges = db.relationship('Charge', backref='service', lazy=True)

class Charge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    period = db.Column(db.Date, nullable=False)  # Период начисления (год-месяц)
    amount = db.Column(db.Float, default=0.0)  # Количество/объем
    total = db.Column(db.Float, default=0.0)  # Сумма: amount * service.rate
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Метод для расчета суммы
    def calculate_total(self):
        if self.amount is not None:
            service = Service.query.get(self.service_id)
            if service and service.rate is not None:
                return self.amount * service.rate
        return 0.0

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), default='bank')  # bank, cash, card
    status = db.Column(db.String(20), default='completed')  # pending, completed, failed
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    report_type = db.Column(db.String(50))  # financial, technical, monthly, annual
    period = db.Column(db.Date)  # Период отчета
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref=db.backref('reports', lazy=True))