# Импорт необходимых классов и модулей
import unittest
from datetime import datetime, timedelta

from bson import ObjectId

from lib.mongo import MongoDB, COLLECTION_CERTS, COLLECTION_USERS


# Инициализация подключения к базе данных c тестом
class TestMongo(unittest.TestCase):
    def setUp(self):
        self.mongo = MongoDB('mongodb://localhost:27017/certificates')
        self.mongo._connect()

    def tearDown(self):
        self.mongo.db.drop_collection(COLLECTION_CERTS)
        self.mongo.db.drop_collection(COLLECTION_USERS)
        self.mongo.close_connections()

    # Тестовые функции
    def test_add_user(self):
        email = "v.onishchuk@centrofinans.ru"
        password = "12345678"
        self.mongo.add_user(email, password)
        user = self.mongo.db[COLLECTION_USERS].find_one({"email": email})
        assert user is not None, "User was not added."
        assert user['email'] == email, "Email does not match."
        print("test_add_user passed")

    def test_add_certificate(self):
        hostname = "example.com"
        common_name = "example"
        expiration_date = datetime.now() + timedelta(days=365)
        serial_number = "123456"
        self.mongo.add_certificate(hostname, common_name, expiration_date, serial_number)
        certificate = self.mongo.db[COLLECTION_CERTS].find_one({"serial_number": serial_number})
        assert certificate is not None, "Certificate was not added."
        assert certificate['hostname'] == hostname, "Hostname does not match."
        print("test_add_certificate passed")

    def test_get_all_certificates(self):
        certificates = self.mongo.get_all_certificates()
        assert certificates is not None, "Failed to retrieve certificates."
        certificates_list = certificates
        print(certificates_list)
        assert isinstance(certificates_list, list), "Certificates should be a list."
        for cert in certificates_list:
            assert 'hostname' in cert, "Certificate should have hostname."
            assert 'common_name' in cert, "Certificate should have common name."
            assert 'expiration_date' in cert, "Certificate should have expiration date."
            assert 'serial_number' in cert, "Certificate should have serial number."
        print("test_get_all_certificates passed")

    def test_get_expiring_certificates_within_days(self):
        days = 60
        expiring_certificates = self.mongo.get_expiring_certificates_within_days(days)
        assert expiring_certificates is not None, "Failed to retrieve expiring certificates."
        assert isinstance(expiring_certificates, list), "Expiring certificates should be a list."
        for cert in expiring_certificates:
            assert 'hostname' in cert, "Certificate should have hostname."
            assert 'common_name' in cert, "Certificate should have common name."
            assert 'expiration_date' in cert, "Certificate should have expiration date."
            assert 'serial_number' in cert, "Certificate should have serial number."
            assert cert['expiration_date'] <= datetime.now() + timedelta(
                days=days), "Certificate expiration date is incorrect."
        print("test_get_expiring_certificates_within_days passed")

    def test_update_certificate(self):
        hostname = "update.com"
        common_name = "update"
        expiration_date = datetime.now() + timedelta(days=180)
        serial_number = "654321"

        r = self.mongo.add_certificate(hostname, common_name, expiration_date, serial_number)
        print(r)

        certificate = self.mongo.db[self.mongo.collection].find_one({"serial_number": serial_number})
        certificate_id = certificate['_id']

        new_hostname = "updated.com"
        self.mongo.update_certificate(
            certificate_id=certificate_id,
            serial_number=serial_number,
            hostname=new_hostname,
            common_name=common_name,
            expiration_date=expiration_date
        )
        updated_certificate = self.mongo.db[COLLECTION_CERTS].find_one({"serial_number": serial_number})
        assert updated_certificate['hostname'] == new_hostname, "Hostname was not updated."
        print("test_update_certificate passed")

    def test_delete_certificate(self):
        certificate_id = "66b0750b3320f85a2c99ca4c"
        self.mongo.delete_certificate(ObjectId(certificate_id))
        deleted_certificate = self.mongo.db[COLLECTION_CERTS].find_one({"_id": ObjectId(certificate_id)})
        assert deleted_certificate is None, "Certificate was not deleted."
        print("test_delete_certificate passed")

    def test_delete_user(self):
        self.mongo.add_user("email@ru", "123")
        user = self.mongo.db[COLLECTION_USERS].find_one({"email": "email@ru"})
        user_id = user['_id']
        self.mongo.delete_user(ObjectId(user_id))
        deleted_user = self.mongo.db[COLLECTION_USERS].find_one({"_id:": ObjectId(user_id)})
        assert deleted_user is None, "User was not deleted."
        print("test_delete_user passed")

    def test_get_certificate(self):
        self.mongo.add_certificate("hostname", "test", datetime.now(), "123")
        r = self.mongo.get_certificate(serial_number="123")
        assert r["serial_number"] == "123"

