from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import requests
import pandas as pd
import os
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

from models.db import db, User, Certificate, Role

URL_YANDEX = "https://botapi.messenger.yandex.net/"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///certificates.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized_callback():
    flash('You must be logged in to view this page.', 'error')
    return redirect(url_for('login'))


def add_certificate(hostname, common_name, expiration_date, serial_number):
    with app.app_context():
        certificate = Certificate(hostname=hostname, common_name=common_name, expiration_date=expiration_date,
                                  serial_number=serial_number)
        db.session.add(certificate)
        db.session.commit()


def get_all_certificates():
    with app.app_context():
        return Certificate.query.all()


def get_expiring_certificates_within_days(days):
    with app.app_context():
        date_later = datetime.now() + timedelta(days=days)
        return Certificate.query.filter(Certificate.expiration_date <= date_later).all()

def _request(url, token, method="GET", **kwargs):
     """Метод отправки запроса"""
    headers = {
        'Authorization': f'OAuth {token}',
        'Content-Type': 'application/json'
    }
    response = requests.requests(url, method, headers=headers, **kwargs)

    if response.status_code == 200:
            app.logger.info("Уведомление успешно отправлено.")
    else:
        app.logger.error(f"Ошибка при отправке уведомления: {response.status_code} {response.text}")
    return response.json()


def send_yandex_notification(message):
    token = ''  # Токен
    url = f'{URL_YANDEX}bot/v1/chats/create/'
    chat_id = '0/0/b06ba50c-e026-43fc-8603-69334b06da5d'  # ID чата

    data = {
        'chat_id': chat_id,
        'text': message
    }

    _request(url=url, token=token, method="POST, json=data)


def create_yandex_notification(chanel_name):
    token = ''  # Токен

    url = f'{URL_YANDEX}bot/v1/messages/sendText/'

    return _request(url=url, token=token, method="POST)




def check_certificates_and_send_notification():
    with app.app_context():
        certificates = get_expiring_certificates_within_days(60)
        if certificates:
            # Отправляем уведомление только если оно еще не было отправлено сегодня
            if not notification_already_sent_today():
                messages = []
                for cert in certificates:
                    messages.append(f"{cert.hostname} истекает {cert.expiration_date.strftime('%d.%m.%Y')}")
                full_message = "\n".join(messages)
                send_yandex_notification(full_message)
                mark_notification_as_sent_today()
        else:
            send_yandex_notification("Нет сертификатов, истекающих в ближайшие 60 дней.")


def notification_already_sent_today():
    # Здесь должна быть проверка, было ли уже отправлено уведомление сегодня
    # Например, можно использовать переменную, файл или базу данных для хранения этого состояния
    return False  # Пока просто возвращаем False


def mark_notification_as_sent_today():
    # Здесь нужно отметить, что уведомление было отправлено сегодня
    # Например, устанавливаем переменную, записываем в файл или обновляем запись в базе данных
    pass  # Пока просто пропускаем эту функцию


@app.route('/yandex_bot_webhook', methods=['POST'])
def yandex_bot_webhook():
    data = request.json
    app.logger.info(f"Получено сообщение: {data}")

    if 'message' in data:
        message_text = data['message']['text']
        if message_text.lower() == 'повторить':
            check_certificates_and_send_notification()

    return jsonify({"status": "ok"})


@app.route('/update_certificate/<int:certificate_id>', methods=['POST'])
@login_required
def update_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    certificate.hostname = request.form['hostname']
    certificate.common_name = request.form['common_name']
    expiration_date_str = request.form['expiration_date']
    certificate.expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
    certificate.serial_number = request.form['serial_number']
    db.session.commit()
    flash('Certificate updated successfully.', 'success')
    return redirect(url_for('view_certificates'))


@app.route('/test_notification', methods=['GET'])
@login_required
def test_notification():
    message = "Это тестовое сообщение от вашего бота."
    response = send_yandex_notification(message)
    return jsonify(response)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/view_certificates', methods=['GET'])
@login_required
def view_certificates():
    with app.app_context():
        certificates = get_all_certificates()
    return render_template('certificates.html', certificates=certificates)


@app.route('/view_expiring_certificates', methods=['GET'])
@login_required
def view_expiring_certificates():
    with app.app_context():
        expiring_certificates = get_expiring_certificates_within_days(60)
    return render_template('certificates.html', certificates=expiring_certificates)


@app.route('/add_certificate', methods=['POST'])
@login_required
def add_cert():
    hostname = request.form['hostname']
    common_name = request.form['common_name']
    expiration_date_str = request.form['expiration_date']
    expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
    serial_number = request.form['serial_number']
    add_certificate(hostname, common_name, expiration_date, serial_number)
    flash('Certificate added successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/edit_certificate/<int:certificate_id>', methods=['GET', 'POST'])
@login_required
def edit_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    if request.method == 'POST':
        certificate.hostname = request.form['hostname']
        certificate.common_name = request.form['common_name']
        expiration_date_str = request.form['expiration_date']
        certificate.expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        certificate.serial_number = request.form['serial_number']
        db.session.commit()
        flash('Certificate updated successfully.', 'success')
        return redirect(url_for('view_certificates'))
    return render_template('edit_certificate.html', certificate=certificate)


@app.route('/delete_certificate/<int:certificate_id>', methods=['POST'])
@login_required
def delete_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    db.session.delete(certificate)
    db.session.commit()
    flash('Certificate deleted successfully.', 'success')
    return redirect(url_for('view_certificates'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash('Login successful.', 'success')
            app.logger.info(f"User {email} logged in successfully.")
            return redirect(url_for('index'))
        else:
            flash('Incorrect email or password.', 'error')
            app.logger.warning(f"Failed login attempt for {email}.")
    return render_template('login2.0.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/export_certificates', methods=['GET'])
@login_required
def export_certificates():
    with app.app_context():
        certificates = get_all_certificates()
        data = []
        for cert in certificates:
            data.append({
                "Hostname": cert.hostname,
                "Common Name": cert.common_name,
                "Expiration Date": cert.expiration_date.strftime('%d.%m.%Y'),
                "Serial Number": cert.serial_number
            })

        df = pd.DataFrame(data)
        file_path = 'certificates.xlsx'
        df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True, download_name='certificates.xlsx')


# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_certificates_and_send_notification, trigger="interval", days=1)
scheduler.start()

# Завершение работы планировщика при завершении приложения
atexit.register(lambda: scheduler.shutdown())

# Отправка уведомления сразу при запуске приложения
#check_certificates_and_send_notification()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)


