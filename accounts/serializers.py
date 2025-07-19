from rest_framework import serializers
from .models import User, PatientProfile, DoctorProfile
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "date_of_birth",
            "address",
            "role",
            "is_active",
        ]
        extra_kwargs = {
            "email": {"read_only": True},
            "role": {"read_only": True},
        }


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
                "validators": [UniqueValidator(queryset=DoctorProfile.objects.all())]
            }
        }


class BaseRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True, validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "password2",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "date_of_birth",
            "address",
        )
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "phone": {"required": True},
        }

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value


class PatientRegistrationSerializer(BaseRegistrationSerializer):
    def create(self, validated_data):
        validated_data.pop("password2")

        user = User.objects.create_user(role=User.Role.PATIENT, **validated_data)
        user.set_password(validated_data["password"])

        PatientProfile.objects.create(user=user)
        return user


class DoctorRegistrationSerializer(BaseRegistrationSerializer):
    license_number = serializers.CharField(write_only=True, required=True)
    specialization = serializers.CharField(write_only=True, required=True)
    consultation_fee = serializers.DecimalField(
        write_only=True, max_digits=8, decimal_places=2, required=True
    )
    availability = serializers.JSONField(write_only=True, required=True)
    description = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta(BaseRegistrationSerializer.Meta):
        fields = BaseRegistrationSerializer.Meta.fields + (
            "license_number",
            "specialization",
            "description",
            "consultation_fee",
            "availability",
        )

    def validate_license_number(self, value):
        if DoctorProfile.objects.filter(license_number=value).exists():
            raise serializers.ValidationError("License number already exists.")
        return value

    def create(self, validated_data):
        doctor_data = {
            "license_number": validated_data.pop("license_number"),
            "specialization": validated_data.pop("specialization"),
            "description": validated_data.pop("description", ""),
            "consultation_fee": validated_data.pop("consultation_fee"),
            "availability": validated_data.pop("availability"),
        }

        validated_data.pop("password2")
        user = User.objects.create_user(role=User.Role.DOCTOR, **validated_data)
        user.set_password(validated_data["password"])

        DoctorProfile.objects.create(user=user, **doctor_data)
        return user


class DoctorPublicSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    profile_photo = serializers.ImageField(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            "first_name",
            "last_name",
            "specialization",
            "description",
            "consultation_fee",
            "profile_photo",
        ]
