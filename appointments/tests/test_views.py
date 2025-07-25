from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta

from accounts.models import User, DoctorProfile
from appointments.models import Appointment, SessionRecord


class BaseAPITestCase(APITestCase):
    """Base test case with common setup for API tests"""

    def setUp(self):
        self.client = APIClient()
        self.now = timezone.now()

        # Create test users
        self.patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT,
        )
        assert self.patient_user, "Patient user creation failed"

        self.doctor_user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR,
        )
        assert self.doctor_user, "Doctor user creation failed"

        DoctorProfile.objects.create(
            user=self.doctor_user,
            verification_status=DoctorProfile.VerificationStatus.APPROVED,
            license_number="DOC12345",
            specialization="Cardiology",
            license_document="doctor_licenses/license.pdf",
            degree_certificate="doctor_degrees/degree.pdf",
            consultation_fee=500.00,
            availability=[{"day": "Monday", "times": ["09:00", "10:00"]}],
        )
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            phone='+1111111111',
            password='testpass123',
            role=User.Role.ADMIN  

        )
        assert self.admin_user is not None, "Admin user creation failed"


        # Create tokens for authentication using simplejwt
        self.patient_token = str(RefreshToken.for_user(self.patient_user).access_token)
        self.doctor_token = str(RefreshToken.for_user(self.doctor_user).access_token)
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)

        # Authentication helpers
        def auth_token(token):
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        self.authenticate_as_patient = lambda: auth_token(self.patient_token)
        self.authenticate_as_doctor = lambda: auth_token(self.doctor_token)
        self.authenticate_as_admin = lambda: auth_token(self.admin_token)
        self.clear_authentication = lambda: self.client.credentials()

        # Common appointment times cached once
        self.future_time = self.now + timedelta(days=7)
        self.past_time = self.now - timedelta(days=7)


class AppointmentCreateViewTest(BaseAPITestCase):
    """Test cases for AppointmentCreateView"""

    def setUp(self):
        super().setUp()
        self.url = reverse('appointments:appointment-create')
        self.valid_data = {
            'doctor': self.doctor_user.id,
            'scheduled_time': self.future_time.isoformat(),
            'duration': 45,
            'reason': 'Follow-up check',
        }

    def test_create_appointment_unauthenticated(self):
        """Ensure unauthenticated user cannot create appointment"""
        self.clear_authentication()
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_create_appointment_invalid_data(self):
        """Ensure invalid data is rejected"""
        self.authenticate_as_patient()
        invalid_data = self.valid_data.copy()
        invalid_data['doctor'] = 99999  # Invalid user id
        invalid_data['scheduled_time'] = 'not-a-datetime'
        response = self.client.post(self.url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('doctor', response.data)
        self.assertIn('scheduled_time', response.data)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_create_appointment_success(self):
        """Test patient can create valid appointment"""
        self.authenticate_as_patient()
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Appointment.objects.count(), 1)
        appointment = Appointment.objects.first()
        self.assertEqual(appointment.patient, self.patient_user)
        self.assertEqual(appointment.doctor.id, self.valid_data['doctor'])

    def test_get_not_allowed(self):
        """GET should not be allowed on appointment create endpoint"""
        self.authenticate_as_patient()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class UpcomingAppointmentsViewTest(BaseAPITestCase):
    """Test cases for UpcomingAppointmentsView"""

    def setUp(self):
        super().setUp()
        self.url = reverse('appointments:upcoming-appointments')

        now = self.now

        # Create appointments with varying properties
        self.upcoming_patient_appt = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(days=1),
            status=Appointment.AppointmentStatus.SCHEDULED,
        )
        self.past_patient_appt = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now - timedelta(days=1),
            status=Appointment.AppointmentStatus.COMPLETED,
        )
        self.cancelled_patient_appt = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(days=2),
            status=Appointment.AppointmentStatus.CANCELLED,
        )
        self.upcoming_doctor_appt = Appointment.objects.create(
            patient=self.admin_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(days=3),
            status=Appointment.AppointmentStatus.SCHEDULED,
        )
        self.upcoming_other_doctor_appt = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.admin_user,
            scheduled_time=now + timedelta(days=4),
            status=Appointment.AppointmentStatus.SCHEDULED,
        )

    def _assert_upcoming_appointments(self, response, expected_ids):
        """Helper to check appointment IDs and fields in paginated response"""
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        results = response.data['results']
        self.assertCountEqual([appt['id'] for appt in results], expected_ids)
        for appt in results:
            self.assertGreaterEqual(appt['scheduled_time'], timezone.now().isoformat())
            self.assertEqual(appt['status'], Appointment.AppointmentStatus.SCHEDULED)

    def test_get_upcoming_appointments_as_patient(self):
        self.authenticate_as_patient()
        response = self.client.get(self.url)
        expected_ids = {self.upcoming_patient_appt.id, self.upcoming_other_doctor_appt.id}
        self._assert_upcoming_appointments(response, expected_ids)

    def test_get_upcoming_appointments_as_doctor(self):
        self.authenticate_as_doctor()
        response = self.client.get(self.url)
        expected_ids = {self.upcoming_patient_appt.id, self.upcoming_doctor_appt.id}
        self._assert_upcoming_appointments(response, expected_ids)

    def test_get_upcoming_appointments_as_admin(self):
        self.authenticate_as_admin()
        response = self.client.get(self.url)
        expected_ids = {
            self.upcoming_patient_appt.id,
            self.upcoming_doctor_appt.id,
            self.upcoming_other_doctor_appt.id,
        }
        self._assert_upcoming_appointments(response, expected_ids)

    def test_get_upcoming_appointments_unauthenticated(self):
        self.clear_authentication()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AppointmentCancelViewTest(BaseAPITestCase):
    """Test cases for AppointmentCancelView"""

    def setUp(self):
        super().setUp()
        self.patient_appt = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.future_time,
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        self.doctor_appt = Appointment.objects.create(
            patient=self.admin_user,
            doctor=self.doctor_user,
            scheduled_time=self.future_time + timedelta(hours=1),
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        self.other_patient_appt = Appointment.objects.create(
            patient=self.admin_user,
            doctor=self.patient_user,
            scheduled_time=self.future_time + timedelta(hours=2),
            status=Appointment.AppointmentStatus.SCHEDULED
        )

    def test_cancel_appointment_as_patient_success(self):
        """Test patient can cancel their own appointment"""
        self.authenticate_as_patient()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.patient_appt.id})
        response = self.client.patch(url, {'reason': 'Changed mind'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.patient_appt.refresh_from_db()
        self.assertEqual(self.patient_appt.status, Appointment.AppointmentStatus.CANCELLED)
        self.assertEqual(self.patient_appt.reason, 'Changed mind')

    def test_cancel_appointment_as_doctor_success(self):
        """Test doctor can cancel their own appointment"""
        self.authenticate_as_doctor()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.doctor_appt.id})
        response = self.client.patch(url, {'reason': 'Doctor unavailable'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doctor_appt.refresh_from_db()
        self.assertEqual(self.doctor_appt.status, Appointment.AppointmentStatus.CANCELLED)
        self.assertEqual(self.doctor_appt.reason, 'Doctor unavailable')

    def test_cancel_appointment_as_admin_success(self):
        """Test admin can cancel any appointment"""
        self.authenticate_as_admin()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.patient_appt.id})
        response = self.client.patch(url, {'reason': 'Admin intervention'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.patient_appt.refresh_from_db()
        self.assertEqual(self.patient_appt.status, Appointment.AppointmentStatus.CANCELLED)
        self.assertEqual(self.patient_appt.reason, 'Admin intervention')

    def test_cancel_appointment_unauthorized(self):
        """Test unauthorized user cannot cancel appointment"""
        self.authenticate_as_patient()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.doctor_appt.id})
        response = self.client.patch(url, {'reason': 'Unauthorized attempt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('You are not authorized', response.data['detail'])
        self.doctor_appt.refresh_from_db()
        self.assertEqual(self.doctor_appt.status, Appointment.AppointmentStatus.SCHEDULED)

    def test_cancel_appointment_unauthenticated(self):
        """Test unauthenticated user cannot cancel appointment"""
        self.clear_authentication()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.patient_appt.id})
        response = self.client.patch(url, {'reason': 'Unauthenticated'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_nonexistent_appointment(self):
        """Test cancelling a nonexistent appointment returns 404"""
        self.authenticate_as_patient()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': 99999})
        response = self.client.patch(url, {'reason': 'Nonexistent'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_appointment_without_reason(self):
        """Test cancelling appointment without providing a reason uses default"""
        self.authenticate_as_patient()
        url = reverse('appointments:appointment-cancel', kwargs={'pk': self.patient_appt.id})
        response = self.client.patch(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.patient_appt.refresh_from_db()
        self.assertEqual(self.patient_appt.status, Appointment.AppointmentStatus.CANCELLED)
        self.assertEqual(self.patient_appt.reason, "Cancelled by user.")


class SessionRecordCreateViewTest(BaseAPITestCase):
    """Test cases for SessionRecordCreateView"""

    def setUp(self):
        super().setUp()
        self.appointment_for_session = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.future_time,
            status=Appointment.AppointmentStatus.COMPLETED,
        )
        self.completed_appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.past_time,
            status=Appointment.AppointmentStatus.COMPLETED
        )
        self.appointment_for_session_other_doctor = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.admin_user,
            scheduled_time=self.now + timedelta(hours=1),
            status=Appointment.AppointmentStatus.COMPLETED,
            duration=30,
            reason="Test appointment",
        )
        self.valid_data = {
            'end_time': (timezone.now() + timedelta(minutes=30)).isoformat(),
            'notes': 'Patient responded well to treatment.',
            'prescription': 'Take medication for 7 days.',
            'diagnosis': 'Mild hypertension',
            'treatment': 'Lifestyle changes and medication',
        }

    def test_create_session_record_success(self):
        """Test doctor can successfully create session record"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.appointment_for_session.id})
        response = self.client.post(url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SessionRecord.objects.count(), 1)
        session_record = SessionRecord.objects.first()
        self.assertEqual(session_record.appointment.id, self.appointment_for_session.id)
        self.assertEqual(session_record.notes, self.valid_data['notes'])
        self.assertEqual(session_record.diagnosis, self.valid_data['diagnosis'])
        self.assertEqual(session_record.treatment, self.valid_data['treatment'])
        self.assertIsNotNone(session_record.start_time)

    def test_create_session_record_unauthenticated(self):
        """Test session record creation by unauthenticated user is forbidden"""
        self.clear_authentication()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.completed_appointment.id})
        response = self.client.post(url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(SessionRecord.objects.count(), 0)

    def test_create_session_record_for_cancelled_appointment_forbidden(self):
        """Session record creation forbidden for cancelled appointment"""
        self.authenticate_as_doctor()

    # Create a fresh appointment with SCHEDULED status
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.now + timedelta(hours=1),
            status=Appointment.AppointmentStatus.SCHEDULED,
    )

    # Transition to CANCELLED (this should be valid from SCHEDULED)
        appointment.status = Appointment.AppointmentStatus.CANCELLED
        appointment.save()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': appointment.id})
        response = self.client.post(url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('completed', response.data['detail'].lower())
        self.assertEqual(SessionRecord.objects.count(), 0)


    def test_create_session_record_for_not_completed_appointment_forbidden(self):
        """Session record creation forbidden for appointment not completed (e.g. scheduled then cancelled)"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.appointment_for_session.id})

        # Force set status to SCHEDULED to bypass transition validation
        Appointment.objects.filter(pk=self.appointment_for_session.pk).update(status=Appointment.AppointmentStatus.SCHEDULED)

        # Now change to CANCELLED (simulate real-world bad status)
        self.appointment_for_session.refresh_from_db()
        self.appointment_for_session.status = Appointment.AppointmentStatus.CANCELLED
        self.appointment_for_session.save()

        response = self.client.post(url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'].lower(), 'can only create session record for completed appointments.')
        self.assertEqual(SessionRecord.objects.count(), 0)

    def test_create_session_record_by_other_doctor_forbidden(self):
        """Test another doctor cannot create session record"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.appointment_for_session_other_doctor.id})
        data = self.valid_data.copy()
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only the assigned doctor can create session records', response.data['detail'])
        self.assertEqual(SessionRecord.objects.count(), 0)

    def test_create_session_record_with_long_notes(self):
        """Test session record creation with very long notes field"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.completed_appointment.id})
        long_notes = 'A' * 5000
        data = self.valid_data.copy()
        data['notes'] = long_notes
        response = self.client.post(url, data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(SessionRecord.objects.count(), 1)
            session_record = SessionRecord.objects.first()
            self.assertEqual(session_record.notes, long_notes)
        else:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(SessionRecord.objects.count(), 0)

    def test_create_session_record_with_invalid_end_time(self):
        """Test session record creation with invalid end_time format"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': self.completed_appointment.id})
        data = self.valid_data.copy()
        data['end_time'] = 'invalid-date-format'
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_time', response.data)
        self.assertEqual(SessionRecord.objects.count(), 0)

    def test_create_session_record_for_nonexistent_appointment(self):
        """Test creating session record for a nonexistent appointment"""
        self.authenticate_as_doctor()
        url = reverse('appointments:session-record-create', kwargs={'appointment_id': 99999})
        response = self.client.post(url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(SessionRecord.objects.count(), 0)
