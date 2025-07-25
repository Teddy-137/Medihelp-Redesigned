from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import serializers
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock
from django.core.validators import RegexValidator

from accounts.serializers import (
    UserSerializer,
    PatientProfileSerializer,
    DoctorProfileSerializer,
    BaseRegistrationSerializer,
    PatientRegistrationSerializer,
    DoctorRegistrationSerializer,
    DoctorPublicSerializer,
)
from accounts.models import User, PatientProfile, DoctorProfile


class UserSerializerTest(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Cina',
            'phone': '+1234567890',
            'gender': User.Gender.MALE.value,
            'date_of_birth': date(1990, 1, 1),
            'address': '123 Main St',
            'role': User.Role.PATIENT,
            'is_active': True,
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_user_serialization(self):
        """Test serializing a User instance"""
        serializer = UserSerializer(self.user)
        data = serializer.data
        
        self.assertEqual(data['email'], self.user_data['email'])
        self.assertEqual(data['first_name'], self.user_data['first_name'])
        self.assertEqual(data['last_name'], self.user_data['last_name'])
        self.assertEqual(data['phone'], self.user_data['phone'])

    def test_user_deserialization_valid(self):
        """Test deserializing valid user data"""
        update_data = {
            'first_name': 'Dear',
            'last_name': 'Mock',
            'phone': '+0987654321',
        }
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_email_read_only(self):
        """Test that email field is read-only"""
        update_data = {
            'email': 'newemail@example.com',
            'first_name': 'Dear',
        }
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')

    def test_role_read_only(self):
        """Test that role field is read-only"""
        update_data = {
            'role': User.Role.DOCTOR,
            'first_name': 'Dear',
        }
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.PATIENT)

    def test_first_name_max_length(self):
        """Test that first_name exceeding max length is invalid"""
        long_name = 'a' * 101  # assuming max_length=100
        update_data = {'first_name': long_name}
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('first_name', serializer.errors)

    def test_phone_format_invalid(self):
        """Test invalid phone format"""
        update_data = {'phone': 'invalid-phone'}
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)

    def test_email_format_invalid(self):
        """Test invalid email format"""
        invalid_data = self.user_data.copy()
        invalid_data['email'] = 'not-an-email'
        serializer = UserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_email_cannot_be_updated(self):
        """Test that email field cannot be updated"""
        serializer = UserSerializer(self.user)
        self.assertTrue(hasattr(serializer.fields['email'], 'read_only') and 
                      serializer.fields['email'].read_only)
        
        update_data = {'email': 'new@example.com', 'first_name': 'Updated'}
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')  # Email unchanged
        self.assertEqual(self.user.first_name, 'Updated')  # Other field updated

    def test_email_read_only(self):
        """Test that email field is read-only through serializer"""
        serializer = UserSerializer(self.user)
        self.assertTrue(hasattr(serializer.fields['email'], 'read_only') and 
                      serializer.fields['email'].read_only)
        
        # Attempt to update email
        update_data = {'email': 'newemail@example.com'}
        serializer = UserSerializer(self.user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)  # Should be valid (email ignored)
        serializer.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')  # Original email remains
        
class PatientProfileSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            gender=User.Gender.FEMALE.value,
            role=User.Role.PATIENT
        )
        self.patient_profile = PatientProfile.objects.create(user=self.user)

    def test_patient_profile_serialization(self):
        """Test serializing a PatientProfile instance"""
        serializer = PatientProfileSerializer(self.patient_profile)
        data = serializer.data
        
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'patient@example.com')
        self.assertEqual(data['user']['first_name'], 'Patient')

    def test_nested_user_read_only(self):
        """Test that nested user field is read-only"""
        update_data = {
            'user': {
                'first_name': 'Updated Name'
            }
        }
        serializer = PatientProfileSerializer(
            self.patient_profile, 
            data=update_data, 
            partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class DoctorProfileSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Abiy',
            phone='+1234567890',
            gender=User.Gender.MALE.value,
            role=User.Role.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={'monday': ['09:00', '17:00']},  # Fixed format
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )

    def test_doctor_profile_serialization(self):
        """Test serializing a DoctorProfile instance"""
        serializer = DoctorProfileSerializer(self.doctor_profile)
        data = serializer.data
        
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'doctor@example.com')
        self.assertEqual(data['license_number'], 'DOC123456')
        self.assertEqual(data['specialization'], 'Cardiology')

    def test_verification_status_read_only(self):
        """Test that verification_status is read-only"""
        update_data = {
            'verification_status': 'VERIFIED',
            'specialization': 'Neurology'
        }
        serializer = DoctorProfileSerializer(
            self.doctor_profile, 
            data=update_data, 
            partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_license_number_unique_validation(self):
        """Test unique validation for license_number"""
        # Create another doctor with different license
        other_user = User.objects.create_user(
            email='other@example.com',
            first_name='Doctor',
            last_name='Abiy',
            phone='+1234567890',
            gender=User.Gender.MALE.value,
            role=User.Role.DOCTOR
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_user,
            license_number='DOC789012',
            specialization='Dermatology',
            consultation_fee=Decimal('100.00'),
            availability={'tuesday': ['10:00', '16:00']},
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )
        
        # Try to update with existing license number
        update_data = {
            'license_number': 'DOC123456'  # Already exists
        }
        serializer = DoctorProfileSerializer(
            other_doctor, 
            data=update_data, 
            partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('license_number', serializer.errors)


class BaseRegistrationSerializerTest(TestCase):
    def setUp(self):
        self.valid_data = {
            'email': 'newuser@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'phone': '+1234567890',
            'gender': User.Gender.MALE.value,
            'date_of_birth': date(1990, 1, 1),
            'address': '123 New St',
        }

    def test_valid_registration_data(self):
        """Test serializer with valid registration data"""
        serializer = BaseRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_password_strength(self):
        invalid_data = self.valid_data.copy()
        invalid_data['password'] = '1234'  # Obviously weak password
        invalid_data['password2'] = '1234'
        serializer = BaseRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_mismatch(self):
        """Test validation when passwords don't match"""
        invalid_data = self.valid_data.copy()
        invalid_data['password2'] = 'DifferentPassword123!'
        
        serializer = BaseRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_write_only(self):
        serializer = BaseRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('password', serializer.data)

    def test_email_unique_validation(self):
        """Test unique email validation"""
        User.objects.create_user(
            first_name='Doctor',
            last_name='Abiy',
            phone='+1234567890',
            email='existing@example.com',
            gender=User.Gender.MALE.value,
            password='password123'
        )
        
        invalid_data = self.valid_data.copy()
        invalid_data['email'] = 'existing@example.com'
        
        serializer = BaseRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_invalid_date_of_birth_type(self):
        invalid_data = self.valid_data.copy()
        invalid_data['date_of_birth'] = 'not-a-date'
        serializer = BaseRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('date_of_birth', serializer.errors)

    def test_required_fields(self):
        """Test that required fields are validated"""
        required_fields = ['email', 'password', 'password2', 'first_name', 'last_name', 'phone']
        
        for field in required_fields:
            incomplete_data = self.valid_data.copy()
            del incomplete_data[field]
            
            serializer = BaseRegistrationSerializer(data=incomplete_data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)

    @patch('django.contrib.auth.password_validation.validate_password')
    def test_password_validation(self, mock_validate):
        mock_validate.side_effect = ValidationError(['Password too weak'])
        invalid_data = self.valid_data.copy()
        invalid_data['password'] = 'weak'
        invalid_data['password2'] = 'weak'
        serializer = BaseRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
class PatientRegistrationSerializerTest(TestCase):
    def setUp(self):
        self.valid_data = {
            'email': 'patient@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'Patient',
            'last_name': 'User',
            'phone': '+1234567890',
            'gender': User.Gender.FEMALE.value,
            'date_of_birth': date(1985, 5, 15),
            'address': '456 sheger St',
        }

    @patch('accounts.models.PatientProfile.objects.create')
    @patch('accounts.models.User.objects.create_user')
    def test_patient_creation(self, mock_create_user, mock_create_profile):
        """Test patient user and profile creation"""
        mock_user = MagicMock()
        mock_create_user.return_value = mock_user
        
        serializer = PatientRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        result = serializer.save()
        
        mock_create_user.assert_called_once()
        call_args = mock_create_user.call_args[1]
        self.assertEqual(call_args['role'], User.Role.PATIENT)
        self.assertEqual(call_args['email'], 'patient@example.com')
        self.assertEqual(call_args['first_name'], 'Patient')
        self.assertEqual(call_args['last_name'], 'User')
        self.assertEqual(call_args['phone'], '+1234567890')
        
        mock_create_profile.assert_called_once_with(user=mock_user)
        mock_user.set_password.assert_called_once_with('StrongPassword123!')

    def test_password2_removed_from_validated_data(self):
        """Test that password2 is removed before user creation"""
        serializer = PatientRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        with patch('accounts.models.User.objects.create_user') as mock_create:
            with patch('accounts.models.PatientProfile.objects.create'):
                serializer.save()
                call_args = mock_create.call_args[1]
                self.assertNotIn('password2', call_args)


class DoctorRegistrationSerializerTest(TestCase):
    def setUp(self):
        self.valid_data = {
            'email': 'doctor@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'Doctor',
            'last_name': 'xyz',
            'phone': '+1234567890',
            'gender': User.Gender.MALE.value,
            'date_of_birth': date(1980, 3, 20),
            'address': '789 hello st',
            'license_number': 'DOC123456',
            'specialization': 'Cardiology',
            'consultation_fee': '200.00',
            'availability': {'monday': ['09:00', '17:00']},
        }

    def test_doctor_fields_in_meta(self):
        """Test that doctor-specific fields are included in Meta.fields"""
        serializer = DoctorRegistrationSerializer()
        expected_fields = (
            'email', 'password', 'password2', 'first_name', 'last_name', 
            'phone', 'gender', 'date_of_birth', 'address',
            'license_number', 'specialization', 'consultation_fee', 'availability', 'description'
        )
        self.assertEqual(serializer.Meta.fields, expected_fields)

    @patch('accounts.models.DoctorProfile.objects.create')
    @patch('accounts.models.User.objects.create_user')
    def test_doctor_creation(self, mock_create_user, mock_create_profile):
        """Test doctor user and profile creation"""
        mock_user = MagicMock()
        mock_create_user.return_value = mock_user
        
        serializer = DoctorRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        result = serializer.save()
        
        mock_create_user.assert_called_once()
        call_args = mock_create_user.call_args[1]
        self.assertEqual(call_args['role'], User.Role.DOCTOR)
        self.assertEqual(call_args['email'], 'doctor@example.com')
        
        mock_create_profile.assert_called_once()
        profile_call_args = mock_create_profile.call_args[1]
        self.assertEqual(profile_call_args['user'], mock_user)
        self.assertEqual(profile_call_args['license_number'], 'DOC123456')
        self.assertEqual(profile_call_args['specialization'], 'Cardiology')
        self.assertEqual(profile_call_args['consultation_fee'], Decimal('200.00'))
        self.assertEqual(profile_call_args['availability'], {'monday': ['09:00', '17:00']})

    def test_required_doctor_fields(self):
        """Test that doctor-specific fields are required"""
        doctor_fields = ['license_number', 'specialization', 'consultation_fee', 'availability']
        
        for field in doctor_fields:
            incomplete_data = self.valid_data.copy()
            del incomplete_data[field]
            
            serializer = DoctorRegistrationSerializer(data=incomplete_data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)

    def test_consultation_fee_validation(self):
        """Test consultation fee decimal validation"""
        invalid_data = self.valid_data.copy()
        invalid_data['consultation_fee'] = 'invalid_decimal'
        
        serializer = DoctorRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('consultation_fee', serializer.errors)

    def test_availability_json_field(self):
        """Test availability JSON field validation"""
        valid_availability = {'monday': ['09:00', '17:00'], 'friday': ['10:00', '14:00']}
        data = self.valid_data.copy()
        data['availability'] = valid_availability
        
        serializer = DoctorRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_optional_fields_missing(self):
        """Test that optional fields can be excluded"""
        optional_fields = ['address']
        for field in optional_fields:
            data = self.valid_data.copy()
            data.pop(field, None)
            serializer = DoctorRegistrationSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)


class DoctorPublicSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='public@example.com',
            first_name='Public',
            last_name='Doctor',
            phone='+1234567890',
            gender=User.Gender.MALE.value,
            role=User.Role.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='PUB123456',
            specialization='General Medicine',
            consultation_fee=Decimal('100.00'),
            availability={'monday': ['09:00', '17:00']},
            profile_photo='path/to/photo.jpg',
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )

    def test_public_serialization(self):
        """Test serializing doctor for public view"""
        serializer = DoctorPublicSerializer(self.doctor_profile)
        data = serializer.data
        
        expected_fields = [
            'first_name', 'last_name', 'specialization', 
            'consultation_fee', 'profile_photo'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        self.assertEqual(data['first_name'], 'Public')
        self.assertEqual(data['last_name'], 'Doctor')
        self.assertEqual(data['specialization'], 'General Medicine')
        self.assertEqual(data['consultation_fee'], '100.00')

    def test_limited_fields_only(self):
        """Test that only specified fields are included"""
        serializer = DoctorPublicSerializer(self.doctor_profile)
        data = serializer.data
        
        excluded_fields = ['license_number', 'user', 'verification_status', 'availability']
        for field in excluded_fields:
            self.assertNotIn(field, data)

    def test_read_only_fields(self):
        """Test that all fields are read-only"""
        update_data = {
            'first_name': 'Updated',
            'specialization': 'Updated Specialization'
        }
        
        serializer = DoctorPublicSerializer(
            self.doctor_profile, 
            data=update_data, 
            partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SerializerIntegrationTest(APITestCase):
    def test_full_patient_registration_flow(self):
        """Test complete patient registration process"""
        registration_data = {
            'email': 'integration@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'Integration',
            'last_name': 'Test',
            'phone': '+1234567890',
            'gender': User.Gender.FEMALE.value,
            'date_of_birth': '1990-01-01',
            'address': '123 Integration St',
        }
        
        serializer = PatientRegistrationSerializer(data=registration_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        user = serializer.save()
        
        self.assertEqual(user.email, 'integration@example.com')
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(user.check_password('StrongPassword123!'))
        self.assertTrue(hasattr(user, 'patient_profile'))

    def test_full_doctor_registration_flow(self):
        """Test complete doctor registration process"""
        registration_data = {
            'email': 'doctor_integration@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'Doctor',
            'last_name': 'Integration',
            'phone': '+1234567890',
            'gender': User.Gender.MALE.value,
            'date_of_birth': '1975-01-01',
            'address': '456 Doctor St',
            'license_number': 'INT123456',
            'specialization': 'Integration Medicine',
            'consultation_fee': '150.00',
            'availability': {'monday': ['09:00', '17:00']},
        }
        
        serializer = DoctorRegistrationSerializer(data=registration_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        user = serializer.save()
        
        self.assertEqual(user.email, 'doctor_integration@example.com')
        self.assertEqual(user.role, User.Role.DOCTOR)
        self.assertTrue(user.check_password('StrongPassword123!'))
        
        doctor_profile = user.doctor_profile 
        self.assertEqual(doctor_profile.license_number, 'INT123456')
        self.assertEqual(doctor_profile.specialization, 'Integration Medicine')
        self.assertEqual(doctor_profile.consultation_fee, Decimal('150.00'))
        self.assertEqual(doctor_profile.availability, {'monday': ['09:00', '17:00']})