from django.urls import path
from .views import (
    PatientRegistrationView,
    DoctorRegistrationView,
    PatientProfileDetailView,
    DoctorProfileDetailView,
    DoctorVerificationView,
    UserDetailView,
)   

urlpatterns = [
    # Registration
    path('register/patient/', PatientRegistrationView.as_view(), name='register-patient'),
    path('register/doctor/', DoctorRegistrationView.as_view(), name='register-doctor'),
    
    # Profile Management
    path('me/', UserDetailView.as_view(), name='user-detail'),
    path('me/patient-profile/', PatientProfileDetailView.as_view(), name='patient-profile'),
    path('me/doctor-profile/', DoctorProfileDetailView.as_view(), name='doctor-profile'),
    
    # Admin Endpoints
    path('admin/verify-doctor/<int:id>/', DoctorVerificationView.as_view(), name='verify-doctor'),
]