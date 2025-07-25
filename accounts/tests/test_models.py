from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from datetime import date

from accounts.models import User, PatientProfile, DoctorProfile

# Get the custom User model
User = get_user_model()


class UserManagerTest(TestCase):
    """Test cases for the custom UserManager"""

    def setUp(self):
        self.base_user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+1234567890',
            'password': 'testpassword123'
        }

    def _create_user(self, **kwargs):
        data = self.base_user_data.copy()
        data.update(kwargs)
        email = data.pop('email')
        first_name = data.pop('first_name')
        last_name = data.pop('last_name')
        phone = data.pop('phone')
        password = data.pop('password')
        return User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            password=password,
            **data
        )

    def _create_superuser(self, **kwargs):
        data = self.base_user_data.copy()
        data.update(kwargs)
        data.setdefault("is_staff", True)
        data.setdefault("is_superuser", True)
        email = data.pop('email')
        first_name = data.pop('first_name')
        last_name = data.pop('last_name')
        phone = data.pop('phone')
        password = data.pop('password')
        return User.objects.create_superuser(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            password=password,
            **data
        )

    def test_create_user_with_valid_data(self):
        """Test creating a user with valid data"""
        user = self._create_user()
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.phone, '+1234567890')
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(user.check_password('testpassword123'))
        self.assertTrue(user.is_active)

    def test_create_user_with_specific_role(self):
        """Test creating a user with a specific role"""
        user = self._create_user(role=User.Role.DOCTOR)
        self.assertEqual(user.role, User.Role.DOCTOR)

    def test_create_user_without_email(self):
        """Test that creating a user without email raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self._create_user(email=None)
        self.assertEqual(str(context.exception), "Users must have an email address")

    def test_create_user_email_normalization(self):
        """Test that email is normalized when creating a user"""
        user = self._create_user(email='Test@EXAMPLE.COM')
        self.assertEqual(user.email, 'Test@example.com')

    def test_create_user_with_extra_fields(self):
        """Test creating a user with extra fields"""
        user = self._create_user(
            gender=User.Gender.FEMALE,
            date_of_birth=date(1990, 1, 1),
            address='123 Main St'
        )
        self.assertEqual(user.gender, User.Gender.FEMALE)
        self.assertEqual(user.date_of_birth, date(1990, 1, 1))
        self.assertEqual(user.address, '123 Main St')

    def test_create_superuser(self):
        """Test creating a superuser"""
        superuser = self._create_superuser()
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_active)
        self.assertEqual(superuser.role, User.Role.ADMIN)

    def test_create_superuser_with_custom_extra_fields(self):
        """Test creating a superuser with custom extra fields"""
        extra_fields = {
            'gender': User.Gender.FEMALE
        }
        superuser = self._create_superuser(**extra_fields)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertEqual(superuser.gender, User.Gender.FEMALE)

    def test_create_superuser_without_is_staff_explicitly_false(self):
        """Test that creating superuser with is_staff=False raises ValueError"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                phone='+1234567890',
                password='adminpass123',
                is_staff=False
            )
        self.assertEqual(str(context.exception), "Superuser must have is_staff=True.")

    def test_create_superuser_without_is_superuser_explicitly_false(self):
        """Test that creating superuser with is_superuser=False raises ValueError"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                phone='+1234567890',
                password='adminpass123',
                is_superuser=False
            )
        self.assertEqual(str(context.exception), "Superuser must have is_superuser=True.")



class UserModelTest(TestCase):
    """Test cases for the User model"""

    def setUp(self):
        self.base_user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+1234567890',
            'gender': User.Gender.MALE,
            'date_of_birth': date(1990, 1, 1),
            'address': '123 Main St',
            'role': User.Role.PATIENT
        }

    def _create_user_with_password(self, password='testpass123', **kwargs):
        data = self.base_user_data.copy()
        data.update(kwargs)
        return User.objects.create_user(**data, password=password)

    def _create_superuser_with_password(self, password='testpass123', **kwargs):
        data = self.base_user_data.copy()
        data.update(kwargs)
        return User.objects.create_superuser(**data, password=password)

    def test_user_creation(self):
        """Test basic user creation"""
        user = self._create_user_with_password()
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.phone, '+1234567890')
        self.assertEqual(user.gender, User.Gender.MALE)
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_user_str_representation(self):
        """Test the string representation of User"""
        user = self._create_user_with_password()
        expected_str = "John Doe <test@example.com>"
        self.assertEqual(str(user), expected_str)

    def test_email_unique_constraint(self):
        """Test that email must be unique"""
        self._create_user_with_password()
        with self.assertRaises(IntegrityError):
            self._create_user_with_password(first_name='Jane')

    def test_username_field_is_email(self):
        """Test that USERNAME_FIELD is set to email"""
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_required_fields(self):
        """Test REQUIRED_FIELDS configuration"""
        expected_fields = ['first_name', 'last_name', 'phone']
        self.assertEqual(User.REQUIRED_FIELDS, expected_fields)

    def test_is_patient_property(self):
        """Test is_patient property"""
        patient_user = self._create_user_with_password(role=User.Role.PATIENT)
        doctor_user = self._create_user_with_password(
            email='doctor@example.com', first_name='Dr', last_name='Smith',
            phone='+0987654321', role=User.Role.DOCTOR
        )
        self.assertTrue(patient_user.is_patient)
        self.assertFalse(doctor_user.is_patient)

    def test_is_doctor_property(self):
        """Test is_doctor property"""
        doctor_user = self._create_user_with_password(
            email='doctor@example.com', first_name='Dr', last_name='Smith',
            phone='+0987654321', role=User.Role.DOCTOR
        )
        self.assertTrue(doctor_user.is_doctor)

    def test_is_doctor_setter_true(self):
        """Test is_doctor setter when set to True"""
        user = self._create_user_with_password(role=User.Role.PATIENT)
        user.is_doctor = True
        self.assertEqual(user.role, User.Role.DOCTOR)

    def test_is_doctor_setter_false(self):
        """Test is_doctor setter when set to False"""
        user = self._create_user_with_password(role=User.Role.DOCTOR)
        user.is_doctor = False
        self.assertEqual(user.role, User.Role.PATIENT)

    def test_is_doctor_setter_false_non_doctor(self):
        """Test is_doctor setter False on non-doctor user"""
        user = self._create_user_with_password(role=User.Role.ADMIN)
        user.is_doctor = False
        self.assertEqual(user.role, User.Role.ADMIN)

    def test_is_admin_property(self):
        """Test is_admin property"""
        admin_user = self._create_superuser_with_password(email='admin@example.com')
        self.assertTrue(admin_user.is_admin)

    def test_can_book_appointment_property(self):
        """Test can_book_appointment property"""
        patient_user = self._create_user_with_password(role=User.Role.PATIENT)
        doctor_user = self._create_user_with_password(
            email='doctor@example.com', first_name='Dr', last_name='Smith',
            phone='+0987654321', role=User.Role.DOCTOR
        )
        self.assertTrue(patient_user.can_book_appointment)
        self.assertFalse(doctor_user.can_book_appointment)

    def test_model_ordering(self):
        """Test model ordering by created_at descending"""
        user1 = self._create_user_with_password(
            email='user1@example.com', first_name='User1', last_name='One',
            phone='+1111111111'
        )
        user2 = self._create_user_with_password(
            email='user2@example.com', first_name='User2', last_name='Two',
            phone='+2222222222'
        )
        users = list(User.objects.all())
        self.assertEqual(users[0], user2)
        self.assertEqual(users[1], user1)

    def test_model_indexes(self):
        """Test that model has expected indexes"""
        indexes = User._meta.indexes
        self.assertEqual(len(indexes), 1)
        email_role_index = indexes[0]
        self.assertEqual(email_role_index.fields, ['email', 'role'])


class UserEnhancementTests(TestCase):
    """Additional tests for core user functionality"""

    def setUp(self):
        self.user_data = {
            'email': 'TestUser@Example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+1234567890',
            'password': 'MyStrongPassword123'
        }

    def test_password_is_hashed(self):
        """Test that the password is hashed and not stored in plain text"""
        user = User.objects.create_user(**self.user_data)
        self.assertNotEqual(user.password, self.user_data['password'])
        self.assertTrue(user.check_password(self.user_data['password']))

    def test_superuser_email_is_normalized(self):
        """Test that superuser email is normalized"""
        superuser = User.objects.create_superuser(
            email='Admin@Example.COM',
            first_name='Admin',
            last_name='User',
            phone='+1987654321',
            password='adminpassword123'
        )
        self.assertEqual(superuser.email, 'Admin@example.com')


class PatientProfileModelTest(TestCase):
    """Test cases for the PatientProfile model"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )

    def test_patient_profile_creation(self):
        """Test basic patient profile creation"""
        profile = PatientProfile.objects.create(
            user=self.user,
            blood_type=PatientProfile.BloodType.A_POSITIVE,
            allergies='Peanuts, Shellfish',
            height=175.5,
            weight=70.2,
            medical_history='No significant history',
            chronic_conditions='None'
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.blood_type, PatientProfile.BloodType.A_POSITIVE)
        self.assertEqual(profile.allergies, 'Peanuts, Shellfish')
        self.assertEqual(profile.height, 175.5)
        self.assertEqual(profile.weight, 70.2)
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

    def test_patient_profile_str_representation(self):
        """Test string representation of PatientProfile"""
        profile = PatientProfile.objects.create(user=self.user)
        expected_str = "Patient: Patient User"
        self.assertEqual(str(profile), expected_str)

    def test_patient_profile_one_to_one_relationship(self):
        """Test OneToOne relationship with User"""
        profile = PatientProfile.objects.create(user=self.user)
        
        # Test forward relationship
        self.assertEqual(profile.user, self.user)
        
        # Test reverse relationship
        self.assertEqual(self.user.patient_profile, profile)

    def test_patient_profile_cascade_delete(self):
        """Test that profile is deleted when user is deleted"""
        profile = PatientProfile.objects.create(user=self.user)
        profile_id = profile.id
        
        # Delete the user
        self.user.delete()
        
        # Profile should also be deleted
        with self.assertRaises(PatientProfile.DoesNotExist):
            PatientProfile.objects.get(id=profile_id)

    def test_blood_type_choices(self):
        """Test blood type field choices"""
        for choice_value, choice_label in PatientProfile.BloodType.choices:
            profile = PatientProfile.objects.create(
                user=self.user,
                blood_type=choice_value
            )
            self.assertEqual(profile.blood_type, choice_value)
            profile.delete()  # Clean up for next iteration

    def test_optional_fields(self):
        """Test that optional fields can be blank/null"""
        profile = PatientProfile.objects.create(user=self.user)
        
        # These fields should be able to be blank/null
        self.assertEqual(profile.blood_type, '')
        self.assertEqual(profile.allergies, '')
        self.assertIsNone(profile.height)
        self.assertIsNone(profile.weight)
        self.assertEqual(profile.medical_history, '')
        self.assertEqual(profile.chronic_conditions, '')

    def test_height_weight_help_text(self):
        """Test help text for height and weight fields"""
        height_field = PatientProfile._meta.get_field('height')
        weight_field = PatientProfile._meta.get_field('weight')
        
        self.assertEqual(height_field.help_text, 'Height in cm')
        self.assertEqual(weight_field.help_text, 'Weight in kg')


class DoctorProfileModelTest(TestCase):
    """Test cases for the DoctorProfile model"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        
        # Create mock files for testing
        self.license_file = SimpleUploadedFile(
            "license.pdf", b"fake license content", content_type="application/pdf"
        )
        self.degree_file = SimpleUploadedFile(
            "degree.pdf", b"fake degree content", content_type="application/pdf"
        )
        self.profile_photo = SimpleUploadedFile(
            "photo.jpg", b"fake image content", content_type="image/jpeg"
        )

    def test_doctor_profile_creation(self):
        """Test basic doctor profile creation"""
        availability = {
            "monday": ["09:00", "14:00"],
            "wednesday": ["10:00", "16:00"]
        }
        
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            license_document=self.license_file,
            degree_certificate=self.degree_file,
            profile_photo=self.profile_photo,
            consultation_fee=Decimal('150.00'),
            availability=availability
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.license_number, 'DOC123456')
        self.assertEqual(profile.specialization, 'Cardiology')
        self.assertEqual(profile.consultation_fee, Decimal('150.00'))
        self.assertEqual(profile.availability, availability)
        self.assertEqual(profile.verification_status, DoctorProfile.VerificationStatus.PENDING)
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

    def test_doctor_profile_str_representation(self):
        """Test string representation of DoctorProfile"""
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        expected_str = "Dr. Doctor Smith (Cardiology)"
        self.assertEqual(str(profile), expected_str)

    def test_doctor_profile_one_to_one_relationship(self):
        """Test OneToOne relationship with User"""
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        
        # Test forward relationship
        self.assertEqual(profile.user, self.user)
        
        # Test reverse relationship
        self.assertEqual(self.user.doctor_profile, profile)

    def test_license_number_unique_constraint(self):
        """Test that license_number must be unique"""
        DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        
        # Create another user and try to use the same license number
        another_user = User.objects.create_user(
            email='another@example.com',
            first_name='Another',
            last_name='Doctor',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        
        with self.assertRaises(IntegrityError):
            DoctorProfile.objects.create(
                user=another_user,
                license_number='DOC123456',  # Same license number
                specialization='Neurology',
                consultation_fee=Decimal('200.00'),
                availability={}
            )

    def test_verification_status_choices(self):
        """Test verification status field choices"""
        for choice_value, choice_label in DoctorProfile.VerificationStatus.choices:
            profile = DoctorProfile.objects.create(
                user=self.user,
                license_number=f'DOC{choice_value}',
                specialization='General Medicine',
                consultation_fee=Decimal('100.00'),
                availability={},
                verification_status=choice_value
            )
            self.assertEqual(profile.verification_status, choice_value)
            profile.delete()  # Clean up for next iteration

    def test_default_verification_status(self):
        """Test default verification status is PENDING"""
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        self.assertEqual(profile.verification_status, DoctorProfile.VerificationStatus.PENDING)

    def test_consultation_fee_decimal_field(self):
        """Test consultation fee decimal field properties"""
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('999999.99'),  # Max value test
            availability={}
        )
        self.assertEqual(profile.consultation_fee, Decimal('999999.99'))

    def test_availability_json_field(self):
        """Test availability JSON field"""
        complex_availability = {
            "monday": ["09:00", "10:00", "14:00", "15:00"],
            "tuesday": ["10:00", "11:00"],
            "wednesday": [],
            "friday": ["09:00", "17:00"]
        }
        
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability=complex_availability
        )
        
        # Retrieve from database to ensure JSON serialization/deserialization works
        profile.refresh_from_db()
        self.assertEqual(profile.availability, complex_availability)

    def test_file_field_help_texts(self):
        """Test help text for file fields"""
        license_field = DoctorProfile._meta.get_field('license_document')
        degree_field = DoctorProfile._meta.get_field('degree_certificate')
        availability_field = DoctorProfile._meta.get_field('availability')
        
        self.assertEqual(license_field.help_text, 'Upload your medical license')
        self.assertEqual(degree_field.help_text, 'Upload your medical degree certificate')
        self.assertIn('available slots', availability_field.help_text)

    def test_model_ordering(self):
        """Test model ordering by created_at descending"""
        profile1 = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        
        # Create another user and profile
        another_user = User.objects.create_user(
            email='another@example.com',
            first_name='Another',
            last_name='Doctor',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        
        profile2 = DoctorProfile.objects.create(
            user=another_user,
            license_number='DOC789012',
            specialization='Neurology',
            consultation_fee=Decimal('200.00'),
            availability={}
        )
        
        profiles = list(DoctorProfile.objects.all())
        # profile2 should come first (more recent)
        self.assertEqual(profiles[0], profile2)
        self.assertEqual(profiles[1], profile1)

    def test_doctor_profile_cascade_delete(self):
        """Test that profile is deleted when user is deleted"""
        profile = DoctorProfile.objects.create(
            user=self.user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={}
        )
        profile_id = profile.id
        
        # Delete the user
        self.user.delete()
        
        # Profile should also be deleted
        with self.assertRaises(DoctorProfile.DoesNotExist):
            DoctorProfile.objects.get(id=profile_id)


class ModelIntegrationTest(TestCase):
    """Integration tests for model relationships and interactions"""

    def test_user_with_patient_profile(self):
        """Test creating a user with patient profile"""
        user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )
        
        profile = PatientProfile.objects.create(
            user=user,
            blood_type=PatientProfile.BloodType.O_POSITIVE,
            height=180.0,
            weight=75.0
        )
        
        # Test relationships
        self.assertEqual(user.patient_profile, profile)
        self.assertEqual(profile.user, user)
        self.assertTrue(user.is_patient)
        self.assertTrue(user.can_book_appointment)

    def test_user_with_doctor_profile(self):
        """Test creating a user with doctor profile"""
        user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        
        profile = DoctorProfile.objects.create(
            user=user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={'monday': ['09:00', '17:00']}
        )
        
        # Test relationships
        self.assertEqual(user.doctor_profile, profile)
        self.assertEqual(profile.user, user)
        self.assertTrue(user.is_doctor)
        self.assertFalse(user.can_book_appointment)

    def test_role_consistency(self):
        """Test that user roles are consistent with their profiles"""
        # Patient user
        patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1111111111',
            password='testpass123',
            role=User.Role.PATIENT
        )
        
        # Doctor user
        doctor_user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='Smith',
            phone='+2222222222',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        
        # Admin user
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            phone='+3333333333',
            password='testpass123'
        )
        
        # Test role properties
        self.assertTrue(patient_user.is_patient)
        self.assertFalse(patient_user.is_doctor)
        self.assertFalse(patient_user.is_admin)
        self.assertTrue(patient_user.can_book_appointment)
        
        self.assertFalse(doctor_user.is_patient)
        self.assertTrue(doctor_user.is_doctor)
        self.assertFalse(doctor_user.is_admin)
        self.assertFalse(doctor_user.can_book_appointment)
        
        self.assertFalse(admin_user.is_patient)
        self.assertFalse(admin_user.is_doctor)
        self.assertTrue(admin_user.is_admin)
        self.assertFalse(admin_user.can_book_appointment)

    def test_multiple_profiles_prevention(self):
        """Test that a user cannot have multiple profiles of the same type"""
        user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            phone='+1234567890',
            password='testpass123'
        )
        
        # Create first patient profile
        PatientProfile.objects.create(user=user)
        
        # Try to create another patient profile for the same user
        with self.assertRaises(IntegrityError):
            PatientProfile.objects.create(user=user)