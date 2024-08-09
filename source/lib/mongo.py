import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId

COLLECTION_CERTS = "certificates"
COLLECTION_USERS = "users"


class MongoDB:
    def __init__(self, mongo_url: str):
        self.mongo_url = mongo_url
        self.connection = None
        self.db = None
        self.col_users = COLLECTION_USERS
        self.collection = COLLECTION_CERTS
        self.logging = logging.getLogger("MongoClient")
        self._connect()

    def _connect(self):
        """Открываем соединение"""
        self.connection = MongoClient(self.mongo_url)
        self.db = self.connection.get_database()

    def close_connections(self):
        """Закрываем соединение"""
        if self.connection is not None:
            self.connection.close()

    def load_user(self, email):
        """Загружает пользователя из базы по email"""
        user = self.db[self.col_users].find_one({"email": email})
        if user:
            return user
        self.logging.warning(f"Пользователь с email {email} не существует")
        return None

    def add_certificate(self, hostname, common_name, expiration_date, serial_number):
        """Добавление сертификата"""
        certificate = {
            "hostname": hostname,
            "common_name": common_name,
            "expiration_date": expiration_date,
            "serial_number": serial_number
        }
        result = self.db[self.collection].insert_one(certificate)
        self.logging.info(f"Added certificate for {hostname} expiring on {expiration_date}")
        return result

    def get_all_certificates(self):
        """Возвращает все сертификаты из базы данных"""
        return list(self.db[self.collection].find())

    def get_certificate(self, serial_number):
        """Возвращает один сертификат из базы данных"""
        return self.db[self.collection].find_one({"serial_number": serial_number})

    def get_expiring_certificates_within_days(self, days):
        """Возвращает сертификаты, срок действия которых истекает в течение указанных дней"""
        date_later = datetime.now() + timedelta(days=days)
        return list(self.db[self.collection].find({"expiration_date": {"$lte": date_later}}))

    def add_user(self, email, password):
        """Вставляет пользователя в коллекцию users"""
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = {
            "email": email,
            "password": hashed_password,
            "active": True
        }
        self.db[self.col_users].insert_one(new_user)
        logging.info(f'User {email} has been created.')

    def update_certificate(self, certificate_id, hostname, common_name, expiration_date, serial_number):
        """Обновляет сертификат по ID"""
        updated_data = {
            "hostname": hostname,
            "common_name": common_name,
            "expiration_date": expiration_date,
            "serial_number": serial_number
        }
        self.db[self.collection].update_one(
            {"_id": ObjectId(certificate_id)},
            {"$set": updated_data}
        )
        self.logging.info(f"Updated certificate {certificate_id} for {hostname}")

    def delete_certificate(self, certificate_id):
        """Удаляет сертификат по ID"""
        self.db[self.collection].delete_one({"_id": certificate_id})
        logging.info(f"Deleted certificate {certificate_id}")

    def delete_user(self, user_id):
        """Удаляет пользователя по ID"""
        self.db[self.col_users].delete_one({"_id": user_id})
        logging.info(f"User {user_id} deleted successfully.")

    # def view_certificates(self):
