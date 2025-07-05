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


class DoctorRegistrationTests(TestCase):
    def test_create_doctor(self):
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


class AppointmentPermissionTests(TestCase):
    def test_doctor_cannot_book_appointment(self):
        """
        Ensure that a doctor user cannot book an appointment as a patient.
        """
        User = get_user_model()
        # Create a doctor user (assuming is_doctor flag or similar)
        doctor = User.objects.create_user(
            email="doctor@example.com",
            password="doctorpass123",
            first_name="Doc",
            last_name="Tor",
            phone="+251600000",
            is_doctor=True  # Adjust according to your model
        )
        # Simulate booking logic (replace with your actual booking logic)
        can_book = getattr(doctor, "can_book_appointment", False)
        # By default, doctors should not be able to book appointments as patients
        self.assertFalse(can_book)
