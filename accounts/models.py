from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(
        self,
        email,
        first_name,
        last_name,
        phone,
        password=None,
        role=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role or self.model.Role.PATIENT,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email, first_name, last_name, phone, password=None, **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        return self.create_user(
            email, first_name, last_name, phone, password, **extra_fields
        )


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        ADMIN = "admin", "Admin"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    gender = models.CharField(max_length=6, choices=Gender.choices, default=Gender.MALE)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PATIENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "role"]),
        ]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"


class PatientProfile(models.Model):
    class BloodType(models.TextChoices):
        A_POSITIVE = "A+", "A+"
        A_NEGATIVE = "A-", "A-"
        B_POSITIVE = "B+", "B+"
        B_NEGATIVE = "B-", "B-"
        AB_POSITIVE = "AB+", "AB+"
        AB_NEGATIVE = "AB-", "AB-"
        O_POSITIVE = "O+", "O+"
        O_NEGATIVE = "O-", "O-"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="patient_profile"
    )
    blood_type = models.CharField(max_length=20, choices=BloodType.choices, blank=True)
    allergies = models.TextField(blank=True)
    height = models.FloatField(null=True, blank=True, help_text="Height in cm")
    weight = models.FloatField(null=True, blank=True, help_text="Weight in kg")
    medical_history = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Patient: {self.user.get_full_name()}"


class DoctorProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    verification_status = models.CharField(
        max_length=11,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    license_number = models.CharField(max_length=50, unique=True)
    specialization = models.CharField(max_length=255)
    license_document = models.FileField(
        upload_to="doctor_licenses/", help_text="Upload your medical license"
    )
    degree_certificate = models.FileField(
        upload_to="doctor_degrees/", help_text="Upload your medical degree certificate"
    )
    profile_photo = models.ImageField(
        upload_to="doctor_profiles/", null=True, blank=True
    )
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2)
    availability = models.JSONField(
        help_text='List of available slots: [{"day": "Monday", "times": ["09:00", "14:00"]}, ...]'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} ({self.specialization})"
