import io
import os
import logging
import atexit
from datetime import datetime

import requests
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    make_response,
    session
)
from flask_oidc import OpenIDConnect

from lib.mongo import MongoDB

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# OpenID Connect configuration
app.config.update({
    'OIDC_CLIENT_SECRETS': {
        'web': {
            'issuer': 'https://oidc.dev.centrofinans.ru/auth/realms/master',
            'auth_uri': 'https://oidc.dev.centrofinans.ru/auth/realms/master/protocol/openid-connect/auth',
            'token_uri': 'https://oidc.dev.centrofinans.ru/auth/realms/master/protocol/openid-connect/token',
            'userinfo_uri': 'https://oidc.dev.centrofinans.ru/auth/realms/master/protocol/openid-connect/userinfo',
            'client_id': 'TimeCertificate',
            'client_secret': os.getenv('OIDC_CLIENT_SECRET'),
        }
    },
    # 'OIDC_ID_TOKEN_COOKIE_SECURE': False,  # Set to True for HTTPS
    'OIDC_SCOPES': ['openid'],
    'MONGO_URI': 'mongodb://localhost:27017/certificates'
})

# Initialize OpenID Connect
oidc = OpenIDConnect(app)

# Initialize MongoDB
mongo = MongoDB(app.config['MONGO_URI'])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)


def add_mchd_to_db(mchd_id, name, date):
    mongo.add_mchd(mchd_id, name, date)


def add_certificate(hostname, common_name, expiration_date, serial_number):
    mongo.add_certificate(hostname, common_name, expiration_date, serial_number)


def get_all_certificates():
    return mongo.get_all_certificates()


def get_expiring_certificates_within_days(days):
    return mongo.get_expiring_certificates_within_days(days)


def send_yandex_request(endpoint, data):
    token = os.getenv('Token_YandexMasage', 'Ключа нет')
    url = f'https://botapi.messenger.yandex.net/bot/v1/{endpoint}'
    headers = {
        'Authorization': f'OAuth {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        logging.info("Запрос успешно выполнен.")
    else:
        logging.error(
            f"Ошибка при выполнении запроса: "
            f"{response.status_code} {response.text}"
        )
    return response.json()


def send_yandex_notification(message):
    chat_id = '0/0/b06ba50c-e026-43fc-8603-69334b06da5d'
    data = {
        'chat_id': chat_id,
        'text': message
    }
    return send_yandex_request('messages/sendText/', data)


def send_mchd_notification(message):
    chat_id = '0/0/b06ba50c-e026-43fc-8603-69334b06da5d'
    data = {
        'chat_id': chat_id,
        'text': message
    }
    return send_yandex_request('messages/sendText/', data)


def check_certificates_and_send_notification():
    certificates = get_expiring_certificates_within_days(60)
    if certificates:
        if not notification_already_sent_today():
            messages = [
                f"{cert['hostname']} истекает {cert['expiration_date'].strftime('%d.%m.%Y')}"
                for cert in certificates
            ]
            full_message = "\n".join(messages)
            send_yandex_notification(full_message)
            mark_notification_as_sent_today()
    else:
        send_yandex_notification("Нет сертификатов, истекающих в ближайшие 60 дней.")


def check_mchd_and_send_notification():
    mchd_list = mongo.get_expiring_mchd_within_days(60)
    if mchd_list:
        if not mchd_notification_already_sent_today():
            messages = [
                f"{mchd['name']} истекает {mchd['timestamp'].strftime('%d.%m.%Y')}"
                for mchd in mchd_list
            ]
            full_message = "\n".join(messages)
            send_mchd_notification(full_message)
            mark_mchd_notification_as_sent_today()
    else:
        send_mchd_notification("Нет МЧД, истекающих в ближайшие 60 дней.")


def mchd_notification_already_sent_today():
    return False


def mark_mchd_notification_as_sent_today():
    pass


def notification_already_sent_today():
    return False


def mark_notification_as_sent_today():
    pass


def add_user(email, password):
    mongo.add_user(email, password)


@app.route('/view_mchd', methods=['GET'])
@oidc.require_login
def view_mchd():
    mchd_list = mongo.get_all_mchd()  # Предполагаем, что есть метод get_all_mchd() в MongoDB
    return render_template('mchd.html', mchd_list=mchd_list)


@app.route('/edit_mchd/<string:mchd_id>', methods=['GET', 'POST'])
@oidc.require_login
def edit_mchd(mchd_id):
    # Получение текущих данных МЧД из базы данных
    mchd = mongo.get_mchd(mchd_id)

    if request.method == 'POST':
        # Извлечение данных из формы
        name = request.form.get('name')
        value = request.form.get('value')  # Добавляем извлечение значения
        date_str = request.form.get('date')

        # Проверка, что все данные присутствуют
        if not name or not value or not date_str:
            flash('Пожалуйста, заполните все поля.', 'error')
            return redirect(url_for('edit_mchd', mchd_id=mchd_id))

        # Преобразование даты
        date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')  # Корректный формат для datetime-local

        # Обновление данных в базе данных
        mongo.update_mchd(mchd_id, name, value, date)  # Убедитесь, что метод обновления принимает эти параметры
        flash('МЧД обновлено успешно.', 'success')
        return redirect(url_for('view_mchd'))

    return render_template('edit_mchd.html', mchd=mchd)  # Передача данных в шаблон


@app.route('/delete_mchd/<string:mchd_id>', methods=['POST'])
@oidc.require_login
def delete_mchd(mchd_id):
    mongo.delete_mchd(mchd_id)  # Предполагаем, что есть метод delete_mchd() в MongoDB
    flash('МЧД удалено успешно.', 'success')
    return redirect(url_for('view_mchd'))


@app.route('/export_certificates')
@oidc.require_login
def export_certificates():
    certificates = get_all_certificates()
    df = pd.DataFrame(certificates)
    """Переименуйте столбцы, если необходимо"""
    df = df.rename(columns={
        '_id': 'ID',
        'hostname': 'Name',
        'expiration_date': 'Expiry Date'
    })
    df['Expiry Date'] = pd.to_datetime(df['Expiry Date']).dt.strftime('%d-%m-%Y')

    """Создаем Excel-файл"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Certificates')
    output.seek(0)

    response = make_response(output.read())
    response.headers['Content-Disposition'] = 'attachment; filename=certificates.xlsx'
    response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response


@app.route('/yandex_bot_webhook', methods=['POST'])
def yandex_bot_webhook():
    data = request.json
    logging.info(f"Получено сообщение: {data}")
    if 'message' in data:
        message_text = data['message']['text']
        if message_text.lower() == 'повторить':
            check_certificates_and_send_notification()
    return jsonify({"status": "ok"})


@app.route('/update_certificate/<string:certificate_id>', methods=['POST'])
@oidc.require_login
def update_certificate(certificate_id):
    certificate = mongo.db[mongo.collection].find_one({"_id": certificate_id})
    if not certificate:
        flash('Certificate not found.', 'error')
        return redirect(url_for('view_certificates'))

    hostname = request.form['hostname']
    common_name = request.form['common_name']
    expiration_date_str = request.form['expiration_date']
    expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
    serial_number = request.form['serial_number']

    mongo.update_certificate(certificate_id, hostname, common_name, expiration_date, serial_number)
    flash('Certificate updated successfully.', 'success')
    logging.info(f"Updated certificate {certificate_id} for {hostname}")
    return redirect(url_for('view_certificates'))


@app.route('/test_notification', methods=['GET'])
@oidc.require_login
def test_notification():
    message = "Это тестовое сообщение от вашего бота."
    response = send_yandex_notification(message)
    return jsonify(response)


@app.route('/')
def index():
    if not oidc.user_loggedin:
        return redirect(url_for('auth'))
    return render_template('index.html')


@app.route('/auth')
def auth():
    return render_template('auth.html')


@app.route('/logout')
def logout():
    """Очистка cookies"""
    response = redirect(url_for('auth'))
    response.set_cookie('session', '', expires=0)

    """Очищаем сессию"""
    session.clear()

    """URL выхода из Keycloak"""
    keycloak_logout_url = 'https://oidc.dev.centrofinans.ru/auth/realms/master/protocol/openid-connect/logout'

    """Перенаправляем на Keycloak для завершения сессии там"""
    return redirect(keycloak_logout_url + '?redirect_uri=' + url_for('auth', _external=True))


@app.route('/view_certificates', methods=['GET'])
@oidc.require_login
def view_certificates():
    all_certs = get_all_certificates()
    return render_template('certificates.html', certificates=all_certs)


@app.route('/view_expiring_certificates', methods=['GET'])
@oidc.require_login
def view_expiring_certificates():
    expiring_certificates = get_expiring_certificates_within_days(60)
    return render_template('expiring_certificates.html', certificates=expiring_certificates)


@app.route('/create_user', methods=['GET', 'POST'])
@oidc.require_login
def create_user():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        add_user(email, password)
        flash('User created successfully.', 'success')
        return redirect(url_for('index'))
    return render_template('create_user.html')


@app.route('/edit_certificate/<string:serial_number>', methods=['GET', 'POST'])
@oidc.require_login
def edit_certificate(serial_number):
    certificate = mongo.get_certificate(serial_number)
    if request.method == 'POST':
        expiration_date_str = request.form['expiration_date']
        expiration_date_new = datetime.strptime(expiration_date_str, '%Y-%m-%d')

        certificate_id = certificate["_id"]

        mongo.update_certificate(
            certificate_id=certificate_id,
            hostname=request.form['hostname'],
            common_name=request.form['common_name'],
            expiration_date=expiration_date_new,
            serial_number=request.form['serial_number']
        )

        flash('Certificate updated successfully.', 'success')
        logging.info(f"Updated certificate {certificate_id} for {certificate['hostname']}")
        return redirect(url_for('view_certificates'))
    return render_template('edit_certificate.html', certificate=certificate)


@app.route('/delete_certificate/<string:serial_number>', methods=['POST'])
@oidc.require_login
def delete_certificate(serial_number):
    certificate = mongo.get_certificate(serial_number)
    if certificate:
        mongo.delete_certificate(certificate['_id'])
        flash('Certificate deleted successfully.', 'success')
    else:
        flash('Certificate not found.', 'error')
    return redirect(url_for('view_certificates'))


@app.route('/delete_user/<string:user_id>', methods=['POST'])
@oidc.require_login
def delete_user(user_id):
    mongo.delete_user(user_id)
    flash('User deleted successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/download_certificates_csv', methods=['GET'])
@oidc.require_login
def download_certificates_csv():
    certificates = list(get_all_certificates())
    df = pd.DataFrame(certificates)
    csv_path = '/mnt/data/certificates.csv'
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)


@app.route('/add_cert', methods=['POST'])
@oidc.require_login
def add_cert():
    hostname = request.form['hostname']
    common_name = request.form['common_name']
    expiration_date_str = request.form['expiration_date']
    expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
    serial_number = request.form['serial_number']

    add_certificate(hostname, common_name, expiration_date, serial_number)

    flash('Сертификат успешно добавлен.', 'success')
    return redirect(url_for('index'))


@app.route('/add_mchd', methods=['POST'])
@oidc.require_login
def add_mchd():
    mchd_id = request.form['mchd_id']
    name = request.form['name']
    date_str = request.form['date']
    date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')  # Обработка даты и времени

    add_mchd_to_db(mchd_id, name, date)

    flash('МЧД успешно добавлен.', 'success')
    return redirect(url_for('view_mchd'))


# Запускаем планировщик задач
scheduler = BackgroundScheduler()
scheduler.add_job(check_certificates_and_send_notification, 'interval', days=1)
scheduler.add_job(check_mchd_and_send_notification, 'interval', days=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Отправка уведомления сразу при запуске приложения
# check_certificates_and_send_notification()
# check_mchd_and_send_notification()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)