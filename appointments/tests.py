from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import DoctorProfile
from .models import Appointment, SessionRecord
from .serializers import AppointmentSerializer, SessionRecordSerializer


User = get_user_model()


class AppointmentSerializerTests(TestCase):
    """Unit-tests focusing on the validation logic found in `AppointmentSerializer`."""

    @classmethod
    def setUpTestData(cls):
        # A dummy PDF file used for FileField requirements on the DoctorProfile
        dummy_file = SimpleUploadedFile("dummy.pdf", b"dummy_content", content_type="application/pdf")

        # Create a doctor (approved) and their profile
        cls.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            password="securepass",
            first_name="Doc",
            last_name="Tor",
            phone="0000000000",
            role=User.Role.DOCTOR,
        )
        cls.approved_profile = DoctorProfile.objects.create(
            user=cls.doctor_user,
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
            license_number="LIC12345",
            specialization="Cardiology",
            license_document=dummy_file,
            degree_certificate=dummy_file,
            consultation_fee=Decimal("100.00"),
            availability=[{"day": "Monday", "times": ["09:00"]}],
        )

        # Create a doctor that is *not* approved
        cls.unapproved_doctor = User.objects.create_user(
            email="pending@example.com",
            password="securepass",
            first_name="Pen",
            last_name="Ding",
            phone="0000000001",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=cls.unapproved_doctor,
            verification_status=DoctorProfile.VerificationStatus.PENDING,
            license_number="LIC67890",
            specialization="Dermatology",
            license_document=dummy_file,
            degree_certificate=dummy_file,
            consultation_fee=Decimal("50.00"),
            availability=[{"day": "Tuesday", "times": ["10:00"]}],
        )

        # Create a patient
        cls.patient_user = User.objects.create_user(
            email="patient@example.com",
            password="patientpass",
            first_name="Pat",
            last_name="Ient",
            phone="0000000002",
            role=User.Role.PATIENT,
        )

    # Helper method to build serializer context mimicking a DRF Request
    def _get_context(self, user):
        class DummyRequest:
            def __init__(self, usr):
                self.user = usr
        return {"request": DummyRequest(user)}

    def test_patient_can_create_valid_appointment(self):
        data = {
            "doctor": self.doctor_user.id,
            "scheduled_time": timezone.now() + timedelta(days=1),
            "duration": 30,
            "reason": "Regular check-up",
        }
        serializer = AppointmentSerializer(data=data, context=self._get_context(self.patient_user))
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)
        appointment = serializer.save(patient=self.patient_user)
        self.assertEqual(appointment.doctor, self.doctor_user)
        self.assertEqual(appointment.patient, self.patient_user)
        self.assertEqual(appointment.status, Appointment.AppointmentStatus.SCHEDULED)

    def test_non_patient_cannot_create_appointment(self):
        """A doctor attempting to create an appointment (acting as patient) should fail."""
        data = {
            "doctor": self.doctor_user.id,
            "scheduled_time": timezone.now() + timedelta(days=1),
            "duration": 30,
        }
        serializer = AppointmentSerializer(data=data, context=self._get_context(self.doctor_user))
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_cannot_book_unapproved_doctor(self):
        data = {
            "doctor": self.unapproved_doctor.id,
            "scheduled_time": timezone.now() + timedelta(days=1),
            "duration": 30,
        }
        serializer = AppointmentSerializer(data=data, context=self._get_context(self.patient_user))
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_conflicting_appointment_rejected(self):
        # First appointment (valid)
        Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=timezone.now() + timedelta(days=2),
            duration=30,
        )

        data = {
            "doctor": self.doctor_user.id,
            "scheduled_time": timezone.now() + timedelta(days=2),
            "duration": 30,
        }
        serializer = AppointmentSerializer(data=data, context=self._get_context(self.patient_user))
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)


class SessionRecordSerializerTests(TestCase):
    """Basic tests for session-record creation and relationship integrity."""

    @classmethod
    def setUpTestData(cls):
        dummy_file = SimpleUploadedFile("dummy.pdf", b"dummy_content", content_type="application/pdf")

        cls.doctor_user = User.objects.create_user(
            email="doc2@example.com",
            password="securepass",
            first_name="Another",
            last_name="Doctor",
            phone="0000000009",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=cls.doctor_user,
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
            license_number="LIC99999",
            specialization="Neurology",
            license_document=dummy_file,
            degree_certificate=dummy_file,
            consultation_fee=Decimal("70.00"),
            availability=[{"day": "Friday", "times": ["11:00"]}],
        )

        cls.patient_user = User.objects.create_user(
            email="pat2@example.com",
            password="pass",
            first_name="Another",
            last_name="Patient",
            phone="0000000010",
            role=User.Role.PATIENT,
        )

        cls.appointment = Appointment.objects.create(
            patient=cls.patient_user,
            doctor=cls.doctor_user,
            scheduled_time=timezone.now() + timedelta(days=5),
            duration=30,
        )

    def test_doctor_can_create_session_record(self):
        data = {
            "end_time": timezone.now() + timedelta(hours=1),
            "notes": "All good!",
            "prescription": "Rest",
        }
        serializer = SessionRecordSerializer(data=data)
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)
        session = serializer.save(appointment=self.appointment, start_time=timezone.now())
        self.assertEqual(session.appointment, self.appointment)
        self.assertEqual(SessionRecord.objects.count(), 1)

    def test_multiple_session_records_not_allowed(self):
        serializer = SessionRecordSerializer(data={})
        serializer.is_valid(raise_exception=True)
        SessionRecord.objects.create(appointment=self.appointment, start_time=timezone.now())

        # second record attempt
        with self.assertRaises(Exception):
            SessionRecord.objects.create(appointment=self.appointment, start_time=timezone.now())
