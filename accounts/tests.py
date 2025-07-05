from django.contrib.auth import get_user_model
from django.test import TestCase

class AccountsTests(TestCase):
    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+251698997",
        )
        self.assertEqual(user.email, "testuser@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertEqual(user.phone, "+251698997")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
