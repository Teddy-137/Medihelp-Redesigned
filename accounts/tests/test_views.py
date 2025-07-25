import pytest
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock

from accounts.models import User, PatientProfile, DoctorProfile
from accounts.serializers import (
    PatientRegistrationSerializer,
    DoctorRegistrationSerializer,
    PatientProfileSerializer,
    DoctorProfileSerializer,
    UserSerializer,
    DoctorPublicSerializer,
)


class BaseAPITestCase(APITestCase):
    """Base test case with common setup for API tests"""
    
    def setUp(self):
        self.client = APIClient()
        
    # Create sample users for our tests.
    # Patient user
        self.patient_user = User.objects.create_user(
            email='patient@example.com',
            first_name='Patient',
            last_name='User',
            phone='+1234567890',
            password='testpass123',
            role=User.Role.PATIENT
        )
        
        # Doctor user
        self.doctor_user = User.objects.create_user(
            email='doctor@example.com',
            first_name='Doctor',
            last_name='xyz',
            phone='+0987654321',
            password='testpass123',
            role=User.Role.DOCTOR
        )

        # Admin user as a superuser
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            phone='+1111111111',
            password='testpass123'
        )
        
        # Create the associated profiles
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            blood_type=PatientProfile.BloodType.A_POSITIVE,
            height=175.0,
            weight=70.0
        )
        
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number='DOC123456',
            specialization='Cardiology',
            consultation_fee=Decimal('150.00'),
            availability={'monday': ['09:00', '17:00']},
            verification_status=DoctorProfile.VerificationStatus.APPROVED
        )
        
        # Create tokens for authentication
        self.patient_access_token = str(RefreshToken.for_user(self.patient_user).access_token)
        self.doctor_access_token = str(RefreshToken.for_user(self.doctor_user).access_token)
        self.admin_access_token = str(RefreshToken.for_user(self.admin_user).access_token)
    # Helper functions below simulating our login routines
    def authenticate_as_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.patient_access_token}')

    def authenticate_as_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.doctor_access_token}')

    def authenticate_as_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access_token}')

    def clear_authentication(self):
        self.client.credentials()

class PatientRegistrationViewTest(BaseAPITestCase):
    """Test cases for PatientRegistrationView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('register-patient')  
        self.valid_data = {
            'email': 'newpatient@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'New',
            'last_name': 'Patient',
            'phone': '+1555555555',
            'gender': 'male',
            'date_of_birth': '1990-01-01',
            'address': '123 New St'
        }

    def test_patient_registration_success(self):
        """Check that registration works correctly for a new patient."""
        response = self.client.post(self.url, self.valid_data, format='json')
            # Basic status and message check

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user_id', response.data)
        self.assertIn('email', response.data)
        self.assertEqual(response.data['email'], 'newpatient@example.com')
        self.assertEqual(response.data['message'], 'Patient registered successfully')
        
        # Verify the new user exists in database
        created_user = User.objects.get(email='newpatient@example.com')
        self.assertEqual(created_user.role, User.Role.PATIENT)
        self.assertTrue(hasattr(created_user, 'patient_profile'))

    def test_patient_registration_invalid_data(self):
        """Test patient registration with invalid data"""
        invalid_data = self.valid_data.copy()
        invalid_data['email'] = 'invalid-email'
        
        response = self.client.post(self.url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_patient_registration_password_mismatch(self):
        """Test patient registration with password mismatch"""
        mismatch_data = self.valid_data.copy()
        mismatch_data['password2'] = 'DifferentPassword123!'

        response = self.client.post(self.url, mismatch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_patient_registration_duplicate_email(self):
        """Test registration fails if email is already taken."""
        duplicate_data = self.valid_data.copy()
        duplicate_data['email'] = 'patient@example.com'  # Already exists in setUp

        response = self.client.post(self.url, duplicate_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_patient_registration_missing_required_fields(self):
        """Test patient registration with missing required fields"""
        incomplete_data = {
            'email': 'incomplete@example.com',
            'password': 'StrongPassword123!'
        }
        
        response = self.client.post(self.url, incomplete_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password2', response.data)
        self.assertIn('first_name', response.data)


class DoctorRegistrationViewTest(BaseAPITestCase):
    """Test cases for DoctorRegistrationView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('register-doctor') 
        self.valid_data = {
            'email': 'newdoctor@example.com',
            'password': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
            'first_name': 'New',
            'last_name': 'Doctor',
            'phone': '+1555555555',
            'gender': 'male',
            'date_of_birth': '1980-01-01',
            'address': '456 Doctor St',
            'license_number': 'NEW123456',
            'specialization': 'General Medicine',
            'consultation_fee': '100.00',
            'availability': {'monday': ['09:00', '17:00']}
        }

    def test_doctor_registration_success(self):
        """Ensure doctor registration works and returns proper pending verification info."""
        
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user_id', response.data)
        self.assertIn('email', response.data)
        self.assertEqual(response.data['email'], 'newdoctor@example.com')
        self.assertEqual(response.data['message'], 'Doctor registered successfully. Account pending verification.')
        
        # Verify user and profile were created
        created_doc = User.objects.get(email='newdoctor@example.com')
        self.assertEqual(created_doc.role, User.Role.DOCTOR)
        self.assertTrue(hasattr(created_doc, 'doctor_profile'))
        self.assertEqual(created_doc.doctor_profile.verification_status, 
                        DoctorProfile.VerificationStatus.PENDING)

    def test_doctor_registration_duplicate_license(self):
        """Test doctor registration with duplicate license number"""
        invalid_data = self.valid_data.copy()
        invalid_data['license_number'] = 'DOC123456'  # Already exists
        
        response = self.client.post(self.url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_registration_missing_doctor_fields(self):
        """Test doctor registration with missing doctor-specific fields"""
        incomplete_data = self.valid_data.copy()
        del incomplete_data['license_number']
        
        response = self.client.post(self.url, incomplete_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('license_number', response.data)


class PatientProfileDetailViewTest(BaseAPITestCase):
    """Test cases for PatientProfileDetailView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('patient-profile') 

    def test_get_patient_profile_authenticated(self):
        """Test retrieving patient profile when authenticated as patient"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], 'patient@example.com')
        self.assertEqual(response.data['blood_type'], PatientProfile.BloodType.A_POSITIVE)

    def test_get_patient_profile_unauthenticated(self):
        """Test retrieving patient profile when not authenticated"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_patient_profile_as_doctor(self):
        """Test retrieving patient profile when authenticated as doctor"""
        self.authenticate_as_doctor()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only patients can access', response.data['detail'])

    def test_update_patient_profile(self):
        """Test updating patient profile"""
        self.authenticate_as_patient()
        
        update_data = {
            'blood_type': PatientProfile.BloodType.B_POSITIVE,
            'height': 180.0,
            'allergies': 'Peanuts'
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['blood_type'], PatientProfile.BloodType.B_POSITIVE)
        self.assertEqual(response.data['height'], 180.0)
        self.assertEqual(response.data['allergies'], 'Peanuts')
    def test_update_patient_profile_as_doctor(self):
        """Doctor should not be able to update patient profile"""
        self.authenticate_as_doctor()
        update_data = {'height': 180.0}
        response = self.client.patch(self.url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_patient_profile_as_admin(self):
        """Test that admin cannot update patient profile through this endpoint"""
        self.authenticate_as_admin()
        
        update_data = {'height': 185.0}
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DoctorProfileDetailViewTest(BaseAPITestCase):
    """Test cases for DoctorProfileDetailView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('doctor-profile')  

    def test_get_doctor_profile_authenticated(self):
        """Test retrieving doctor profile when authenticated as doctor"""
        self.authenticate_as_doctor()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], 'doctor@example.com')
        self.assertEqual(response.data['license_number'], 'DOC123456')
        self.assertEqual(response.data['specialization'], 'Cardiology')

    def test_get_doctor_profile_as_patient(self):
        """Test retrieving doctor profile when authenticated as patient"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only doctors can access', response.data['detail'])

    def test_update_doctor_profile(self):
        """Test updating doctor profile"""
        self.authenticate_as_doctor()
        
        update_data = {
            'specialization': 'Neurology',
            'consultation_fee': '200.00',
            'availability': {'tuesday': ['10:00', '16:00']}
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['specialization'], 'Neurology')
        self.assertEqual(response.data['consultation_fee'], '200.00')

    def test_update_doctor_profile_verification_status_readonly(self):
        """Test that verification_status cannot be updated by doctor"""
        self.authenticate_as_doctor()
        
        update_data = {
            'verification_status': DoctorProfile.VerificationStatus.APPROVED,
            'specialization': 'Updated Specialization'
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verification status should remain unchanged
        self.doctor_profile.refresh_from_db()
        self.assertEqual(self.doctor_profile.verification_status, 
                        DoctorProfile.VerificationStatus.APPROVED)


class DoctorVerificationViewTest(BaseAPITestCase):
    """Test cases for DoctorVerificationView"""
    
    def setUp(self):
        super().setUp()
        # Create a pending doctor for verification
        self.pending_doctor_user = User.objects.create_user(
            email='pending@example.com',
            first_name='Pending',
            last_name='Doctor',
            phone='+2222222222',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.pending_doctor_profile = DoctorProfile.objects.create(
            user=self.pending_doctor_user,
            license_number='PENDING123',
            specialization='Dermatology',
            consultation_fee=Decimal('120.00'),
            availability={'wednesday': ['09:00', '17:00']},
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )
        self.url = reverse('verify-doctor', 
                          kwargs={'id': self.pending_doctor_profile.id})

    def test_verify_doctor_as_admin(self):
        """Test verifying doctor as admin"""
        self.authenticate_as_admin()
        
        update_data = {
            'verification_status': DoctorProfile.VerificationStatus.APPROVED
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('verification status updated', response.data['message'])
        self.assertEqual(response.data['status'], 'approved')
        
        # Verify database was updated
        self.pending_doctor_profile.refresh_from_db()
        self.assertEqual(self.pending_doctor_profile.verification_status, 
                        DoctorProfile.VerificationStatus.APPROVED)

    def test_reject_doctor_as_admin(self):
        """Test rejecting doctor as admin"""
        self.authenticate_as_admin()
        
        update_data = {
            'verification_status': DoctorProfile.VerificationStatus.REJECTED
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'rejected')

    def test_verify_doctor_as_non_admin(self):
        """Test that non-admin cannot verify doctor"""
        self.authenticate_as_patient()
        
        update_data = {
            'verification_status': DoctorProfile.VerificationStatus.APPROVED
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_doctor_invalid_status(self):
        """Test verifying doctor with invalid status"""
        self.authenticate_as_admin()
        
        update_data = {
            'verification_status': 'invalid_status'
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid verification status', response.data['error'])

    def test_verify_doctor_unauthenticated(self):
        """Test verifying doctor without authentication"""
        update_data = {
            'verification_status': DoctorProfile.VerificationStatus.APPROVED
        }
        
        response = self.client.patch(self.url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    def test_verify_nonexistent_doctor(self):
        """Test verifying a doctor with nonexistent ID returns 404"""
        self.authenticate_as_admin()

        # Try to verify a doctor with ID that does not exist
        url = reverse('verify-doctor', kwargs={'id': 99999})  # ID 99999 likely doesn't exist
        update_data = {
        'verification_status': DoctorProfile.VerificationStatus.APPROVED
         }

        response = self.client.patch(url, update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserDetailViewTest(BaseAPITestCase):
    """Test cases for UserDetailView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('user-detail')  # Adjust URL name as needed

    def test_get_user_detail_as_patient(self):
        """Test retrieving user details as patient"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'patient@example.com')
        self.assertEqual(response.data['first_name'], 'Patient')
        self.assertEqual(response.data['role'], User.Role.PATIENT)

    def test_get_user_detail_as_doctor(self):
        """Test retrieving user details as doctor"""
        self.authenticate_as_doctor()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'doctor@example.com')
        self.assertEqual(response.data['role'], User.Role.DOCTOR)

    def test_get_user_detail_unauthenticated(self):
        """Test retrieving user details without authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_detail_read_only_fields(self):
        """Test that email and role are read-only"""
        self.authenticate_as_patient()
        
        # GET request should work
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # POST, PUT, PATCH should not be allowed (method not allowed)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class DoctorListViewTest(BaseAPITestCase):
    """Test cases for DoctorListView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('doctor-list')  
        
        # Create additional doctors for testing
        self.doctor2_user = User.objects.create_user(
            email='doctor2@example.com',
            first_name='Second',
            last_name='Doctor',
            phone='+3333333333',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.doctor2_profile = DoctorProfile.objects.create(
            user=self.doctor2_user,
            license_number='DOC789012',
            specialization='Neurology',
            consultation_fee=Decimal('200.00'),
            availability={'friday': ['10:00', '16:00']},
            verification_status=DoctorProfile.VerificationStatus.APPROVED
        )
        
        # Create a pending doctor (should not appear in list)
        self.pending_doctor_user = User.objects.create_user(
            email='pending@example.com',
            first_name='Pending',
            last_name='Doctor',
            phone='+4444444444',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.pending_doctor_profile = DoctorProfile.objects.create(
            user=self.pending_doctor_user,
            license_number='PENDING123',
            specialization='Dermatology',
            consultation_fee=Decimal('120.00'),
            availability={'monday': ['09:00', '17:00']},
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )

    def test_get_doctor_list_authenticated(self):
        """Test retrieving doctor list when authenticated"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)  # Paginated response
        self.assertEqual(len(response.data['results']), 2)  # Only approved doctors
        
        # Check that only approved doctors are returned
        doctor_emails = [doc['first_name'] for doc in response.data['results']]
        self.assertIn('Doctor', doctor_emails)
        self.assertIn('Second', doctor_emails)

    def test_get_doctor_list_unauthenticated(self):
        """Test retrieving doctor list without authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_doctor_list_filtering_by_specialization(self):
        """Test filtering doctors by specialization"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url, {'specialization': 'Cardiology'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['specialization'], 'Cardiology')

    def test_doctor_list_search_by_name(self):
        """Test searching doctors by name"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url, {'search': 'Second'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['first_name'], 'Second')

    def test_doctor_list_ordering_by_fee(self):
        """Test ordering doctors by consultation fee"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url, {'ordering': 'consultation_fee'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        # Should be ordered by fee ascending
        self.assertLessEqual(float(results[0]['consultation_fee']), 
                           float(results[1]['consultation_fee']))

    def test_doctor_list_pagination(self):
        """Test pagination of doctor list"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url, {'page_size': 1})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('next', response.data)
        self.assertIsNotNone(response.data['next'])

    def test_doctor_list_public_fields_only(self):
        """Test that only public fields are returned"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doctor_data = response.data['results'][0]
        
        # Check that no private field is leaked
        unexpected_fields = ['license_number', 'verification_status', 'user', 'availability']
        for field in unexpected_fields:
            self.assertNotIn(field, doctor_data)

        # Check that the public fields are present
        expected_fields = ['first_name', 'last_name', 'specialization', 'consultation_fee', 'profile_photo']
        for field in expected_fields:
            self.assertIn(field, doctor_data)


class DoctorDetailViewTest(BaseAPITestCase):
    """Test cases for DoctorDetailView"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('doctor-detail', 
                          kwargs={'id': self.doctor_profile.id})
        
        # Create a pending doctor for testing access control
        self.pending_doctor_user = User.objects.create_user(
            email='pending@example.com',
            first_name='Pending',
            last_name='Doctor',
            phone='+4444444444',
            password='testpass123',
            role=User.Role.DOCTOR
        )
        self.pending_doctor_profile = DoctorProfile.objects.create(
            user=self.pending_doctor_user,
            license_number='PENDING123',
            specialization='Dermatology',
            consultation_fee=Decimal('120.00'),
            availability={'monday': ['09:00', '17:00']},
            verification_status=DoctorProfile.VerificationStatus.PENDING
        )
        self.pending_url = reverse('doctor-detail', 
                                  kwargs={'id': self.pending_doctor_profile.id})

    def test_get_approved_doctor_detail(self):
        """Test retrieving approved doctor detail"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Doctor')
        self.assertEqual(response.data['specialization'], 'Cardiology')
        self.assertEqual(response.data['consultation_fee'], '150.00')

    def test_get_pending_doctor_detail_forbidden(self):
        """Test that pending doctor detail is not accessible"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.pending_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_doctor_detail_unauthenticated(self):
        """Test retrieving doctor detail without authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_nonexistent_doctor_detail(self):
        """Test retrieving nonexistent doctor detail"""
        self.authenticate_as_patient()
        
        nonexistent_url = reverse('doctor-detail', kwargs={'id': 99999})
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaginationTest(BaseAPITestCase):
    """Test cases for StandardResultsSetPagination"""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('doctor-list')
        
        # Create multiple approved doctors for pagination testing
        for i in range(15):
            user = User.objects.create_user(
                email=f'doctor{i}@example.com',
                first_name=f'Doctor{i}',
                last_name='Test',
                phone=f'+555000{i:04d}',
                password='testpass123',
                role=User.Role.DOCTOR
            )
            DoctorProfile.objects.create(
                user=user,
                license_number=f'DOC{i:06d}',
                specialization='General Medicine',
                consultation_fee=Decimal('100.00'),
                availability={'monday': ['09:00', '17:00']},
                verification_status=DoctorProfile.VerificationStatus.APPROVED
            )

    def test_default_pagination(self):
        """Test default pagination settings"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)  # Default page size
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('count', response.data)

    def test_custom_page_size(self):
        """Test custom page size parameter"""
        self.authenticate_as_patient()
        
        response = self.client.get(self.url, {'page_size': 5})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)

    def test_pagination_navigation(self):
        """Test pagination navigation"""
        self.authenticate_as_patient()
        
        # Get first page
        response = self.client.get(self.url, {'page_size': 5})
        self.assertEqual(len(response.data['results']), 5)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        
        # Get second page
        response = self.client.get(self.url, {'page': 2, 'page_size': 5})
        self.assertEqual(len(response.data['results']), 5)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNotNone(response.data['previous'])


class ErrorHandlingTest(BaseAPITestCase):
    """Test cases for error handling"""
    
    def test_404_error_handling(self):
        """Test 404 error handling"""
        self.authenticate_as_patient()
        
        nonexistent_url = '/api/nonexistent-endpoint/'
        response = self.client.get(nonexistent_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_method_not_allowed(self):
        """Test method not allowed error"""
        self.authenticate_as_patient()
        user_detail_url = reverse('user-detail')
        response = self.client.post(user_detail_url, {})
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_permission_denied_custom_message(self):
        """Test custom permission denied messages"""
        self.authenticate_as_doctor()
        
        patient_profile_url = reverse('patient-profile')
        response = self.client.get(patient_profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only patients can access', response.data['detail'])