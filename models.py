from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)  # Добавили is_active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # Flask-Login требует эти методы
    def get_id(self):
        return str(self.id)
    
    # Указываем что пользователь активен
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