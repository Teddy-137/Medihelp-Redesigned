from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from accounts.models import User, DoctorProfile
from appointments.models import Appointment, SessionRecord
from appointments.serializers import (
    AppointmentSerializer,
    SessionRecordSerializer,
    AppointmentCancelSerializer,
    UpcomingAppointmentSerializer,
)

class AppointmentSerializerTest(TestCase):
    """Test cases for AppointmentSerializer"""

    def setUp(self):
        self.factory = APIRequestFactory()

        # Create test users and profiles
        self.patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )
        self.doctor_user_approved = User.objects.create_user(
            email='doctor_approved@example.com',
            first_name='Approved',
            last_name='Doctor',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.doctor_profile_approved = DoctorProfile.objects.create(
            user=self.doctor_user_approved,
            license_number='DOC111',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={},
            verification_status=DoctorProfile.VerificationStatus.APPROVED
        )

        self.doctor_user_pending = User.objects.create_user(
            email='doctor_pending@example.com',
            first_name='Pending',
            last_name='Doctor',
            phone='+0987654322',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.doctor_profile_pending = DoctorProfile.objects.create(
            user=self.doctor_user_pending,
            license_number='DOC222',
            specialization='Neurology',
            consultation_fee=Decimal('100.00'),
            availability={},
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )

        self.doctor_user = self.doctor_user_approved 

        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.ADMIN,
            is_staff=True
        )

        # Use timezone-aware datetimes
        self.current_time = timezone.now()
        self.future_time = self.current_time + timedelta(days=1)
        self.past_time = self.current_time - timedelta(days=1)

        self.appointment_data = {
            'doctor': self.doctor_user_approved.id,
            'scheduled_time': self.future_time.isoformat(),
            'duration': 30,
            'reason': 'Initial consultation'
        }

        # Create an appointment in the future to avoid validation errors
        self.existing_appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user_approved,
            scheduled_time=self.future_time + timedelta(hours=1),
            duration=30,
            reason="Existing appointment",
            status=Appointment.AppointmentStatus.SCHEDULED
        )

    def get_serializer_context(self, user):
        """Helper to create serializer context with a mock request"""
        request = self.factory.post('/')
        request.user = user
        return {'request': request}

    def test_appointment_serialization(self):
        """Test serialization of an Appointment instance"""
        
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user_approved,
            scheduled_time=self.future_time,
            duration=30,
            reason="Test reason",
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        serializer = AppointmentSerializer(appointment)
        data = serializer.data

        self.assertEqual(data['id'], appointment.id)
        self.assertEqual(data['patient'], self.patient_user.id)
        # self.assertEqual(data['doctor'], self.doctor_user_approved.id)
        self.assertEqual(data['patient_name'], f"{self.patient_user.first_name} {self.patient_user.last_name}")
        self.assertEqual(data['doctor_name'], f"{self.doctor_user_approved.first_name} {self.doctor_user_approved.last_name}")
        self.assertEqual(data['doctor_specialization'], 'Cardiology')
        self.assertEqual(data['status'], Appointment.AppointmentStatus.SCHEDULED)
        self.assertIsNotNone(data['created_at']) 


    def test_appointment_deserialization_valid(self):
        """Test deserialization with valid data"""
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=self.appointment_data, context=context)
        self.assertTrue(serializer.is_valid(),serializer.errors)
        self.assertEqual(serializer.validated_data['doctor'], self.doctor_user_approved)
        self.assertEqual(serializer.validated_data['scheduled_time'], self.future_time)

    def test_patient_field_ignored_on_input_and_set_from_context(self):
        """Test that the patient field is ignored from input data because it's read_only,
        and is correctly set from the request user during creation."""
        data = self.appointment_data.copy()
        data['patient'] = self.admin_user.id 
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('patient', serializer.validated_data)
        appointment = serializer.save()
        self.assertEqual(appointment.patient, self.patient_user)

    def test_non_patient_cannot_book_appointment(self):
        """Test that only patient users can book appointments."""
        non_patient_users = [self.doctor_user_approved, self.admin_user]
        for user in non_patient_users:
            with self.subTest(user_role=user.role):
                context = self.get_serializer_context(user)
                serializer = AppointmentSerializer(data=self.appointment_data, context=context)
                self.assertFalse(serializer.is_valid())
                self.assertIn("non_field_errors", serializer.errors) # Error from validate()
                self.assertIn("Only patients can book appointments.", str(serializer.errors['non_field_errors']))
        
    def test_status_read_only(self):
        """Test that status field is read-only"""
        data = self.appointment_data.copy()
        data['status'] = Appointment.AppointmentStatus.COMPLETED
        
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('status', serializer.validated_data)

    def test_doctor_must_be_in_doctor_role(self):
        non_doctor_user = User.objects.create_user(
            email='nondoctor@example.com',
            first_name='Non',
            last_name='Doctor',
            phone='+11111111111',
            password='testpass123',
            role=User.Role.PATIENT,  # Not a doctor
        )
        invalid_data = self.appointment_data.copy()
        invalid_data['doctor'] = non_doctor_user.id

        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('doctor', serializer.errors)

    def test_validate_doctor_not_approved(self):
        """Test validation: doctor must be approved"""
        invalid_data = self.appointment_data.copy()
        invalid_data['doctor'] = self.doctor_user_pending.id

        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn("doctor", serializer.errors)
        self.assertIn("Doctor is not approved", str(serializer.errors['doctor']))

    
    def test_validate_scheduled_time_in_past(self):
        """Test validation: scheduled time must be in the future"""
        invalid_data = self.appointment_data.copy()
        invalid_data['scheduled_time'] = self.past_time.isoformat()
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn("scheduled_time", serializer.errors)
        self.assertIn("Scheduled time must be in the future", str(serializer.errors['scheduled_time']))

    
    def test_validate_conflicting_appointments(self):
        """Test validation: no conflicting appointments for the doctor"""
        # Create an appointment that conflicts with the new one
        Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user_approved,
            scheduled_time=self.future_time,
            duration=30,
            reason="Conflicting appointment",
            status=Appointment.AppointmentStatus.SCHEDULED
        )

        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=self.appointment_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertIn("Doctor is not available at this time", str(serializer.errors['non_field_errors']))

    
    def test_validate_no_conflict_with_cancelled_appointment(self):
        """Test that cancelled appointments don't cause conflicts"""
        # Create a cancelled appointment at the same time
        Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user_approved,
            scheduled_time=self.future_time,
            duration=30,
            reason="Cancelled appointment",
            status=Appointment.AppointmentStatus.CANCELLED
        )

        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=self.appointment_data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_duration_min_value(self): 
        """Test that duration must be positive and respect min value"""
        invalid_data = self.appointment_data.copy()
        invalid_data['duration'] = 0
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('duration', serializer.errors)
        self.assertIn("Ensure this value is greater than or equal to 10.", str(serializer.errors['duration']))

    def test_validate_duration_max_value(self):
        """Test that duration has a reasonable maximum"""
        invalid_data = self.appointment_data.copy()
        invalid_data['duration'] = 241  # Exceeds max of 240 minutes
        
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('duration', serializer.errors)
        self.assertIn("Ensure this value is less than or equal to 240.", str(serializer.errors['duration']))

    def test_validate_reason_max_length(self):
        """Test reason field max length validation"""
        invalid_data = self.appointment_data.copy()
        invalid_data['reason'] = 'a' * 501  # Exceeds max_length=500
        
        context = self.get_serializer_context(self.patient_user)
        serializer = AppointmentSerializer(data=invalid_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('reason', serializer.errors)
        self.assertIn("Ensure this field has no more than 500 characters", str(serializer.errors['reason']))

    
    def test_create_appointment(self):
        """Test that serializer creates an appointment correctly"""
        
        context = self.get_serializer_context(self.patient_user) 
        serializer = AppointmentSerializer(data=self.appointment_data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        appointment = serializer.save()
        
        # Verify all fields
        self.assertEqual(appointment.patient, self.patient_user)
        self.assertEqual(appointment.doctor, self.doctor_user_approved)
        self.assertEqual(appointment.scheduled_time, self.future_time)
        self.assertEqual(appointment.duration, 30)
        self.assertEqual(appointment.reason, 'Initial consultation')
        self.assertEqual(appointment.status, Appointment.AppointmentStatus.SCHEDULED)

class SessionRecordSerializerTest(TestCase):
    """Test cases for SessionRecordSerializer"""

    def setUp(self):
        self.patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )
        self.doctor_user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number='DOC456',
            specialization='Pediatrics',
            consultation_fee=Decimal('120.00'),
            availability={},
            verification_status=DoctorProfile.VerificationStatus.APPROVED
        )
        
        self.current_time = timezone.now()
        # Create appointment in the future to avoid validation errors
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.current_time + timedelta(hours=1),
            duration=30,
            reason="Test appointment",
            status=Appointment.AppointmentStatus.COMPLETED
        )
        self.start_time = self.current_time
        self.end_time = self.current_time + timedelta(minutes=30)

        self.session_record_data = {
            'appointment': self.appointment.id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'notes': 'Patient felt better after consultation.',
            'prescription': 'Take paracetamol.',
            "diagnosis": "Migraine",
            "treatment": "Painkillers"
        }

    
    def test_session_record_serialization(self):
        """Test serialization of a SessionRecord instance"""
        
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            end_time=self.end_time,
            notes='Test notes',
            prescription='Test prescription',
            diagnosis="Patient diagnosed with flu.",
            treatment="Rest and hydration",
        )
        serializer = SessionRecordSerializer(session_record)
        data = serializer.data

        self.assertEqual(data['id'], session_record.id)
        self.assertEqual(data['appointment'], self.appointment.id)
        self.assertEqual(data['start_time'], self.start_time.isoformat().replace('+00:00', 'Z'))
        self.assertEqual(data['end_time'], self.end_time.isoformat().replace('+00:00', 'Z'))
        self.assertEqual(data['notes'], 'Test notes')
        self.assertEqual(data['prescription'], 'Test prescription')
        self.assertEqual(data['created_at'], session_record.created_at.isoformat().replace('+00:00', 'Z'))


    def test_session_record_deserialization_valid(self):
        """Test deserialization with valid data"""
        
        data_for_deserialization = {
            'end_time': (self.current_time + timedelta(minutes=30)).isoformat(),
            'notes': 'Patient felt better after consultation.',
            'prescription': 'Take paracetamol.',
            'diagnosis': 'Migraine',
            'treatment': 'Painkillers'
        }
        context = {
            'appointment': self.appointment,
            'start_time': self.current_time
        }
        serializer = SessionRecordSerializer(data=data_for_deserialization, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_appointment_read_only(self):
        """Test that appointment field is read-only"""
        data = {
            'end_time': self.end_time.isoformat(),
            'notes': 'Test notes',
            'prescription': 'Test prescription',
            'diagnosis': 'Test diagnosis',
            'treatment': 'Test treatment'
        }
        context = {'appointment': self.appointment}
        serializer = SessionRecordSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_start_time_read_only(self):
        """Test that start_time field is read-only"""
        data = {
            'end_time': self.end_time.isoformat(),
            'notes': 'Test notes',
            'diagnosis': 'Cold',
            'treatment': 'Rest and fluids'
        }
        context = {'start_time': self.current_time}
        serializer = SessionRecordSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_end_time_after_start(self):
        """Test that end_time must be after start_time"""
        data = {
            'end_time': (self.current_time - timedelta(minutes=30)).isoformat(),
            'notes': 'Test notes',
            'prescription': 'Test prescription',
            'diagnosis': 'Test diagnosis',
            'treatment': 'Test treatment'
        }
        context = {
            'appointment': self.appointment,
            'start_time': self.current_time
        }
        serializer = SessionRecordSerializer(data=data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('end_time', serializer.errors)
        self.assertIn("End time must be after start time", str(serializer.errors['end_time']))

    def test_validate_notes_max_length(self):
        """Test notes field max length validation"""
        data = {
            'end_time': self.end_time.isoformat(),
            'notes': 'a' * 1001  # Exceeds max_length=1000
        }
        context = {'appointment': self.appointment}
        serializer = SessionRecordSerializer(data=data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('notes', serializer.errors)
        self.assertIn("Ensure this field has no more than 1000 characters", str(serializer.errors['notes']))

    def test_create_session_record(self):
        """Test that serializer creates a session record correctly"""
        data = {
            'end_time': (self.current_time + timedelta(minutes=30)).isoformat(),
            'notes': 'Test notes',
            'prescription': 'Test prescription',
            'diagnosis': 'Flu',
            'treatment': 'Medication and rest'
        }
        
        context = {
            'appointment': self.appointment,
            'start_time': self.current_time
        }
        serializer = SessionRecordSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        session_record = serializer.save(
            appointment=self.appointment,
            start_time=self.current_time
        )
        self.assertEqual(session_record.appointment, self.appointment)
        self.assertEqual(session_record.start_time, self.current_time)
        self.assertEqual(session_record.end_time, self.current_time + timedelta(minutes=30))
        self.assertEqual(session_record.notes, 'Test notes')


class AppointmentCancelSerializerTest(TestCase):
    """Test cases for AppointmentCancelSerializer"""

    def test_cancel_serializer_with_reason(self):
        """Test serializer with a reason provided"""
        data = {'reason': 'Patient requested cancellation.'}
        serializer = AppointmentCancelSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['reason'], 'Patient requested cancellation.')

    def test_cancel_serializer_without_reason(self):
        """Test serializer without a reason """
        data = {}
        serializer = AppointmentCancelSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get('reason'))

    def test_cancel_serializer_with_blank_reason(self):
        """Test serializer with a blank reason (allow_blank=True)"""
        data = {'reason': ''}
        serializer = AppointmentCancelSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['reason'], '')

    def test_cancel_serializer_reason_max_length(self):
        """Test reason field max length validation"""
        data = {'reason': 'a' * 256}
        serializer = AppointmentCancelSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Ensure this field has no more than 255 characters.",
            str(serializer.errors['reason'])
        )


class UpcomingAppointmentSerializerTest(TestCase):
    """Test cases for UpcomingAppointmentSerializer"""

    def setUp(self):
        self.current_time = timezone.now()
        
        self.patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )
        self.doctor_user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number='DOC456',
            specialization='Pediatrics',
            consultation_fee=Decimal('120.00'),
            availability={},
            verification_status=DoctorProfile.VerificationStatus.APPROVED
        )
        self.future_time = self.current_time + timedelta(days=2)
        self.past_time = self.current_time - timedelta(days=1)
        
        # Create upcoming appointment in the future
        self.upcoming_appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.future_time,
            duration=60,
            reason="Annual check-up",
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        
        # Create past appointment by first creating it in the future then updating
        self.past_appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.future_time,
            duration=30,
            reason="Follow-up",
            status=Appointment.AppointmentStatus.COMPLETED
        )
        # Update to past time after creation to avoid validation error
        Appointment.objects.filter(id=self.past_appointment.id).update(
            scheduled_time=self.past_time
        )
        self.past_appointment.refresh_from_db()


    def test_upcoming_appointment_serialization(self):
        """Test serialization for upcoming appointments"""
        serializer = UpcomingAppointmentSerializer(self.upcoming_appointment)
        data = serializer.data

        self.assertEqual(data['id'], self.upcoming_appointment.id)
        self.assertEqual(data['scheduled_time'], self.future_time.isoformat().replace('+00:00', 'Z'))
        self.assertEqual(data['duration'], 60)
        self.assertEqual(data['reason'], 'Annual check-up')
        self.assertEqual(data['status'], Appointment.AppointmentStatus.SCHEDULED)
        self.assertEqual(data['patient_name'], 'Patient User')
        self.assertEqual(data['doctor_name'], 'Doctor Smith')
        self.assertEqual(data['doctor_specialization'], 'Pediatrics')

    def test_upcoming_appointment_field_inclusion(self):
        """Test that only specified fields are included"""
        serializer = UpcomingAppointmentSerializer(self.upcoming_appointment)
        data = serializer.data

        expected_fields = {
            'id', 'scheduled_time', 'duration', 'reason', 'status',
            'patient_name', 'doctor_name', 'doctor_specialization'
        }
        self.assertCountEqual(data.keys(), expected_fields)

    
    def test_past_appointment_serialization(self):
        """Test that past appointments are serialized correctly"""        
        serializer = UpcomingAppointmentSerializer(self.past_appointment)
        data = serializer.data

        self.assertEqual(data['id'], self.past_appointment.id)
        self.assertEqual(data['scheduled_time'], self.past_time.isoformat().replace('+00:00', 'Z'))
        self.assertEqual(data['status'], Appointment.AppointmentStatus.COMPLETED)