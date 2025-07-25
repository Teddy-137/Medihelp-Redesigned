from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from appointments.models import Appointment, SessionRecord


class AppointmentModelTest(TestCase):
    """Test cases for the Appointment model"""

    def setUp(self):
        self.now = timezone.now()
        # Create patient and doctor users for use in tests
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
        self.scheduled_time = self.now + timedelta(days=1)

    def test_appointment_creation(self):
        """Test basic appointment creation with all fields provided"""
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
            duration=45,
            status=Appointment.AppointmentStatus.SCHEDULED,
            reason="Routine check-up"
        )
        self.assertEqual(appointment.patient, self.patient_user)
        self.assertEqual(appointment.doctor, self.doctor_user)
        self.assertEqual(appointment.scheduled_time, self.scheduled_time)
        self.assertEqual(appointment.duration, 45)
        self.assertEqual(appointment.status, Appointment.AppointmentStatus.SCHEDULED)
        self.assertEqual(appointment.reason, "Routine check-up")
        self.assertIsNotNone(appointment.created_at)
        self.assertIsNotNone(appointment.updated_at)

    def test_appointment_default_values(self):
        """Test default duration (30) and status (SCHEDULED)"""
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
        )
        self.assertEqual(appointment.duration, 30)
        self.assertEqual(appointment.status, Appointment.AppointmentStatus.SCHEDULED)
        self.assertIsNone(appointment.reason)

    def test_appointment_str_representation(self):
        """Test string output of Appointment object"""
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
        )
        expected_str = (
            f"Appointment #{appointment.id}: "
            f"{self.patient_user.get_full_name()} with {self.doctor_user.get_full_name()} "
            f"at {self.scheduled_time}"
        )
        self.assertEqual(str(appointment), expected_str)

    def test_appointment_status_choices(self):
        """Test that Appointment supports all defined status choices"""
        for choice_value, _ in Appointment.AppointmentStatus.choices:
            appointment = Appointment.objects.create(
                patient=self.patient_user,
                doctor=self.doctor_user,
                scheduled_time=self.scheduled_time,
                status=choice_value
            )
            self.assertEqual(appointment.status, choice_value)
            appointment.delete()

    def test_past_appointment_validation(self):
        """Test that creating appointments in the past raises ValidationError"""
        past_time = timezone.now() - timedelta(hours=1)
        appointment = Appointment(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=past_time,
            duration=30
        )
        with self.assertRaises(ValidationError) as context:
            appointment.full_clean()
    
        self.assertIn("Cannot schedule an appointment in the past.", str(context.exception))

    def test_valid_status_transitions(self):
        """Test allowed status transitions (e.g., SCHEDULED → COMPLETED)"""
        valid_transitions = [
            Appointment.AppointmentStatus.COMPLETED,
            Appointment.AppointmentStatus.CANCELLED,
            Appointment.AppointmentStatus.NOSHOW,
        ]
        for new_status in valid_transitions:
            with self.subTest(f"SCHEDULED → {new_status}"):
                appointment = Appointment.objects.create(
                    patient=self.patient_user,
                    doctor=self.doctor_user,
                    scheduled_time=timezone.now() + timedelta(hours=1),
                    status=Appointment.AppointmentStatus.SCHEDULED
                )
                appointment.status = new_status
                appointment.full_clean()  
                appointment.save()

    def test_invalid_status_transitions(self):
        """Test that invalid status transitions raise ValidationError"""
        invalid_transitions = [
            (Appointment.AppointmentStatus.CANCELLED, Appointment.AppointmentStatus.SCHEDULED),
            (Appointment.AppointmentStatus.COMPLETED, Appointment.AppointmentStatus.SCHEDULED),
            (Appointment.AppointmentStatus.NOSHOW, Appointment.AppointmentStatus.COMPLETED),
        ]

        for from_status, to_status in invalid_transitions:
            with self.subTest(f"{from_status} → {to_status}"):
                # Create appointment in initial state
                appointment = Appointment.objects.create(
                    patient=self.patient_user,
                    doctor=self.doctor_user,
                    scheduled_time=self.scheduled_time,
                    status=from_status  
                )
                appointment.status = to_status
                with self.assertRaises(ValidationError) as cm:
                    appointment.full_clean()
                    appointment.save()
                self.assertIn("Invalid status transition", str(cm.exception))
                appointment.delete()

    def test_appointment_end_time_property(self):
        """Test that the end_time property returns scheduled_time + duration"""
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
            duration=45
        )
        expected_end_time = self.scheduled_time + timedelta(minutes=45)
        self.assertEqual(appointment.end_time, expected_end_time)

    def test_save_triggers_validation_error_for_past_appointment(self):
        """Saving an appointment scheduled in the past should raise ValidationError"""
        past_time = self.now - timedelta(hours=1)
        appointment = Appointment(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=past_time
        )
        with self.assertRaises(ValidationError) as cm:
            appointment.save()
        self.assertIn("Cannot schedule an appointment in the past.", str(cm.exception))

    # def test_invalid_status_transition_error_message(self):
        # """Check that invalid status transition raises ValidationError with proper message"""
        # appointment = Appointment.objects.create(
        #     patient=self.patient_user,
        #     doctor=self.doctor_user,
        #     scheduled_time=self.scheduled_time,
        #     status=Appointment.AppointmentStatus.CANCELLED
        # )
        # appointment.status = Appointment.AppointmentStatus.SCHEDULED
        # with self.assertRaises(ValidationError) as cm:
        #     appointment.full_clean()
        # self.assertIn("Invalid status transition", str(cm.exception))

    def test_appointment_foreign_keys_cascade_delete(self):
        """Test that deleting patient or doctor also deletes the appointment"""
        # Test patient delete
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
        )
        appointment_id = appointment.id
        self.patient_user.delete()
        with self.assertRaises(Appointment.DoesNotExist):
            Appointment.objects.get(id=appointment_id)

        self.patient_user = User.objects.create_user(
            email='patient2@example.com',
            first_name='Patient2',
            last_name='User2',
            phone='+1234567891',
            password='testpass123',
            role=User.Role.PATIENT
        )
        self.doctor_user = User.objects.create_user(
            email='doctor2@example.com',
            first_name='Doctor2',
            last_name='Smith2',
            phone='+0987654322',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
        )
        appointment_id = appointment.id
        self.doctor_user.delete()
        with self.assertRaises(Appointment.DoesNotExist):
            Appointment.objects.get(id=appointment_id)

    def test_appointment_related_names(self):
        """Test related_name attributes: patient_appointments and doctor_appointments"""
        appointment1 = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
        )
        appointment2 = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time + timedelta(hours=1),
        )
        self.assertIn(appointment1, self.patient_user.patient_appointments.all())
        self.assertIn(appointment2, self.patient_user.patient_appointments.all())
        self.assertEqual(self.patient_user.patient_appointments.count(), 2)

        self.assertIn(appointment1, self.doctor_user.doctor_appointments.all())
        self.assertIn(appointment2, self.doctor_user.doctor_appointments.all())
        self.assertEqual(self.doctor_user.doctor_appointments.count(), 2)

    def test_appointment_model_ordering(self):
        """Test appointments are ordered by scheduled_time descending"""
        now = self.now
        appointment1 = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(hours=3),
        )
        appointment2 = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(hours=2),
        )
        appointment3 = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=now + timedelta(hours=1),
        )
        appointments = list(Appointment.objects.all())
        self.assertEqual(appointments[0], appointment1)
        self.assertEqual(appointments[1], appointment2)
        self.assertEqual(appointments[2], appointment3)

    def test_appointment_model_indexes(self):
        """Test that indexes on scheduled_time and status exist"""
        indexes = Appointment._meta.indexes
        fields = [index.fields for index in indexes]
        self.assertIn(['scheduled_time'], fields)
        self.assertIn(['status'], fields)


class SessionRecordModelTest(TestCase):
    """Test cases for the SessionRecord model"""

    def setUp(self):
        # Create test users and appointment
        self.now = timezone.now()
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
        self.scheduled_time = self.now + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
            status=Appointment.AppointmentStatus.COMPLETED
        )
        self.start_time = self.scheduled_time
        self.end_time = self.scheduled_time + timedelta(minutes=30)

    def test_session_record_creation(self):
        """Test basic creation of a session record"""
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            end_time=self.end_time,
            notes="Patient presented with mild symptoms.",
            prescription="Rest and fluids.",
            diagnosis="Migraine",
            treatment="Painkillers and rest"
        )
        self.assertEqual(session_record.appointment, self.appointment)
        self.assertEqual(session_record.start_time, self.start_time)
        self.assertEqual(session_record.end_time, self.end_time)
        self.assertEqual(session_record.notes, "Patient presented with mild symptoms.")
        self.assertEqual(session_record.prescription, "Rest and fluids.")
        self.assertIsNotNone(session_record.created_at)

    def test_session_record_optional_fields(self):
        """Test that end_time, notes, and prescription can be left blank"""
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        self.assertIsNone(session_record.end_time)
        self.assertEqual(session_record.notes, "")
        self.assertEqual(session_record.prescription, "")

    def test_session_record_str_representation(self):
        """Test string output of SessionRecord object"""
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        expected_str = f"Session for Appointment #{self.appointment.id}"
        self.assertEqual(str(session_record), expected_str)

    def test_session_record_one_to_one_relationship(self):
        """Test OneToOne link between appointment and session record"""
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        self.assertEqual(session_record.appointment, self.appointment)
        self.assertEqual(self.appointment.session_record, session_record)

    def test_session_record_cascade_delete(self):
        """Test that deleting an appointment deletes its session record"""
        session_record = SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        session_record_id = session_record.id
        self.appointment.delete()
        with self.assertRaises(SessionRecord.DoesNotExist):
            SessionRecord.objects.get(id=session_record_id)

    def test_session_record_unique_per_appointment(self):
        """Test that only one session record can exist per appointment"""
        SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.start_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        duplicate_record = SessionRecord(
            appointment=self.appointment,
            start_time=self.start_time + timedelta(minutes=1),
            diagnosis="Duplicate diagnosis",
            treatment="Duplicate treatment"
        )
        with self.assertRaises(ValidationError):
            duplicate_record.full_clean()

    def test_session_record_requires_diagnosis_and_treatment(self):
        """SessionRecord must have diagnosis and treatment"""
        session_record = SessionRecord(
            appointment=self.appointment,
            start_time=self.scheduled_time,
        )
        with self.assertRaises(ValidationError) as cm:
            session_record.full_clean()
        self.assertIn('diagnosis', cm.exception.message_dict)
        self.assertIn('treatment', cm.exception.message_dict)

    def test_session_record_only_for_completed_appointment(self):
        """SessionRecord can only be created for completed appointments"""
        scheduled_appointment = Appointment.objects.create(
            patient=self.patient_user,
            doctor=self.doctor_user,
            scheduled_time=self.scheduled_time,
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        session_record = SessionRecord(
            appointment=scheduled_appointment,
            start_time=self.scheduled_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        with self.assertRaises(ValidationError) as cm:
            session_record.full_clean()
        self.assertIn("appointment", cm.exception.message_dict)
        self.assertIn("Can only create session records for completed appointments", str(cm.exception))

    def test_session_record_end_time_after_start_time_validation(self):
        """End time must be after start time for SessionRecord"""
        session_record = SessionRecord(
            appointment=self.appointment,
            start_time=self.scheduled_time + timedelta(hours=1),
            end_time=self.scheduled_time,
            diagnosis="Test diagnosis",
            treatment="Test treatment"
        )
        with self.assertRaises(ValidationError) as cm:
            session_record.full_clean()
        self.assertIn('end_time', cm.exception.message_dict)
        self.assertIn('End time must be after start time.', str(cm.exception))

    def test_session_record_uniqueness_raises_on_save(self):
        """Saving a duplicate SessionRecord for the same appointment raises ValidationError"""
        SessionRecord.objects.create(
            appointment=self.appointment,
            start_time=self.scheduled_time,
            diagnosis="Diagnosis 1",
            treatment="Treatment 1"
        )
        duplicate = SessionRecord(
            appointment=self.appointment,
            start_time=self.scheduled_time + timedelta(minutes=2),
            diagnosis="Diagnosis 2",
            treatment="Treatment 2"
        )
        with self.assertRaises(ValidationError):
            duplicate.save()
