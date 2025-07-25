from rest_framework import serializers
from .models import User, PatientProfile, DoctorProfile
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.validators import UniqueValidator
from django.core.validators import EmailValidator, RegexValidator

class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be in format: '+999999999'."
            )
        ],
        required=True
    )
    email = serializers.EmailField(
        validators=[
            EmailValidator(message="Enter a valid email address.")
        ]
    )

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone", "gender",
            "date_of_birth", "address", "role", "is_active"
        ]
        read_only_fields = ['role'] 
        extra_kwargs = {
                "email": {"read_only": True},
                "first_name": {"required": True, "max_length": 100},
                "last_name": {"required": True},
            }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:  # if updating
            self.fields['email'].read_only = True

    def update(self, instance, validated_data):
        validated_data.pop('email', None)
        return super().update(instance, validated_data)

class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = PatientProfile
        fields = "__all__"

class DoctorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    verification_status = serializers.CharField(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = "__all__"
        extra_kwargs = {
            "license_number": {
                "validators": [
                    UniqueValidator(
                        queryset=DoctorProfile.objects.all(),
                        message="This license number is already registered."
                    )
                ]
            }
        }

class BaseRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this email already exists."
            )
        ]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = (
            "email", "password", "password2", "first_name", "last_name",
            "phone", "gender", "date_of_birth", "address"
        )
        extra_kwargs = {
            "phone": {
                "required": True,
                "validators": [
                    RegexValidator(
                        regex=r'^\+?1?\d{9,15}$',
                        message="Phone number must be in format: '+999999999'."
                    )
                ]
            },
        }

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        try:
            validate_password(attrs["password"], user=None)
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        
        return attrs

class PatientRegistrationSerializer(BaseRegistrationSerializer):
    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(
            role=User.Role.PATIENT,
            **validated_data
        )
        user.set_password(validated_data["password"])
        PatientProfile.objects.create(user=user)
        return user

class DoctorRegistrationSerializer(BaseRegistrationSerializer):
    license_number = serializers.CharField(
        write_only=True,
        required=True,
        validators=[
            UniqueValidator(
                queryset=DoctorProfile.objects.all(),
                message="This license number is already registered."
            )
        ]
    )
    specialization = serializers.CharField(write_only=True, required=True)
    consultation_fee = serializers.DecimalField(
        write_only=True,
        max_digits=8,
        decimal_places=2,
        required=True
    )
    availability = serializers.JSONField(write_only=True, required=True)
    description = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )


    class Meta(BaseRegistrationSerializer.Meta):
        fields = BaseRegistrationSerializer.Meta.fields + (
            "license_number", "specialization",
            "consultation_fee", "availability", "description"
        )

    def create(self, validated_data):
        doctor_data = {
            "license_number": validated_data.pop("license_number"),
            "specialization": validated_data.pop("specialization"),
            "consultation_fee": validated_data.pop("consultation_fee"),
            "availability": validated_data.pop("availability"),
        }

        validated_data.pop("password2")
        user = User.objects.create_user(
            role=User.Role.DOCTOR,
            **validated_data
        )
        user.set_password(validated_data["password"])
        DoctorProfile.objects.create(user=user, **doctor_data)
        return user

class DoctorPublicSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')

    class Meta:
        model = DoctorProfile
        fields = [
            'first_name', 'last_name', 'specialization',
            'consultation_fee', 'profile_photo'
        ]