from app import app, db
from models import User

with app.app_context():
    # Создаем оператора, если его нет
    if not User.query.filter_by(username='operator').first():
        operator = User(
            username='operator',
            email='operator@example.com',
            role='operator'  # Устанавливаем роль оператора
        )
        operator.set_password('operator123')
        db.session.add(operator)
        db.session.commit()
        print('Оператор создан')