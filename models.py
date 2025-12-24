# models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    # Роли пользователей
    role = db.Column(db.String(20), default='user')  # 'user', 'operator', 'admin'
    
    # Личная информация
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    
    # Для обратной совместимости
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_operator(self):
        return self.role in ['operator', 'admin']
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}, role: {self.role}>'

class House(db.Model):
    __tablename__ = 'houses'
    
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    area = db.Column(db.Float, nullable=False)  # Площадь в м²
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Дополнительная информация
    floor = db.Column(db.Integer)
    rooms = db.Column(db.Integer)
    residents_count = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('houses', lazy=True))
    
    def __repr__(self):
        return f'<House {self.address}>'

class Receipt(db.Model):
    __tablename__ = 'receipts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    house_id = db.Column(db.Integer, db.ForeignKey('houses.id'))
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    
    # Статус оплаты
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)
    
    # Дата выставления и срок оплаты
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    
    # Детали квитанции
    period_start = db.Column(db.DateTime)  # Период начала
    period_end = db.Column(db.DateTime)    # Период окончания
    receipt_type = db.Column(db.String(50))  # Тип квитанции
    
    user = db.relationship('User', backref=db.backref('receipts', lazy=True))
    house = db.relationship('House', backref=db.backref('receipts', lazy=True))
    
    @property
    def days_overdue(self):
        if self.is_paid:
            return 0    
        if not self.due_date:
            return 0
        from datetime import datetime
        delta = datetime.utcnow().date() - self.due_date.date()
        return delta.days if delta.days > 0 else 0

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    description = db.Column(db.Text)
    
    # Связь с квитанцией
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'))
    
    # Способ оплаты
    payment_method = db.Column(db.String(50))  # card, cash, bank_transfer
    
    user = db.relationship('User', backref=db.backref('payments', lazy=True))
    receipt = db.relationship('Receipt', backref=db.backref('payments', lazy=True))
    
    def __repr__(self):
        return f'<Payment {self.id}, amount: {self.amount}, status: {self.status}>'

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    report_type = db.Column(db.String(50))  # financial, technical, complaints
    
    author = db.relationship('User', backref=db.backref('reports', lazy=True))
    
    def __repr__(self):
        return f'<Report {self.id}, title: {self.title}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Приоритет и статус
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    status = db.Column(db.String(20), default='pending')   # pending, in_progress, completed
    
    # Назначение
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Даты
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    assigned_user = db.relationship('User', backref=db.backref('tasks', lazy=True))
    
    def __repr__(self):
        return f'<Task {self.id}, title: {self.title}, status: {self.status}>'