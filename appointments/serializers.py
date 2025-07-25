from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Appointment, SessionRecord
from accounts.models import User ,DoctorProfile
from rest_framework.exceptions import ValidationError


class AppointmentSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.DOCTOR), write_only=True)
    doctor_name = serializers.CharField(source="doctor.get_full_name", read_only=True)
    doctor_specialization = serializers.CharField(source="doctor.doctor_profile.specialization", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "doctor",
            "scheduled_time",
            "duration",
            "reason",
            "status",
            "created_at",
            "patient_name",
            "doctor_name",
            "doctor_specialization",
        ]
        extra_kwargs = {  
            "status": {"read_only": True},
            "duration": {"min_value": 10, "max_value": 240},
            "reason": {"max_length": 500},
        }

    def validate(self, data):
        user = self.context['request'].user

        if not getattr(user, "is_patient", False):
            raise ValidationError("Only patients can book appointments.")

        # Doctor validation
        doctor = data.get("doctor")
        if not doctor:
            raise serializers.ValidationError({"doctor": "Doctor is required"})

        if (
            doctor.doctor_profile.verification_status
            != DoctorProfile.VerificationStatus.APPROVED
        ):
            raise serializers.ValidationError({"doctor": "Doctor is not approved"})

        # Time validation
        scheduled_time = data.get("scheduled_time")
        if scheduled_time and scheduled_time < timezone.now():
            raise serializers.ValidationError(
                {"scheduled_time": "Scheduled time must be in the future"}
            )
        duration = data.get("duration")
        # Conflict check 
        if scheduled_time and duration and doctor:
            end_time = scheduled_time + timedelta(minutes=duration)
            conflicting_appointments = Appointment.objects.filter(
                doctor=doctor,
                scheduled_time__lt=end_time,
                status=Appointment.AppointmentStatus.SCHEDULED,
            ).exclude(pk=self.instance.pk if self.instance else None)

            for appt in conflicting_appointments:
                appt_end_time = appt.scheduled_time + timedelta(minutes=appt.duration)
                if scheduled_time < appt_end_time:
                    raise serializers.ValidationError(
                        {"non_field_errors": ["Doctor is not available at this time"]}
                    )

        return data
    def validate_scheduled_time(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future")
        return value


    def create(self, validated_data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError({"non_field_errors": ["Request context is missing"]})

        user = request.user

        if not getattr(user, "is_patient", False):
            raise serializers.ValidationError({"patient": "Only patients can create appointments"})

        # Assign the patient to the requesting user, ignore any patient data from input
        validated_data['patient'] = user

        # Validate doctor profile presence (optional)
        doctor = validated_data.get('doctor')
        if doctor and not getattr(doctor, 'doctor_profile', None):
            raise serializers.ValidationError({"doctor": "Doctor must have a profile"})

        return super().create(validated_data)


class SessionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRecord
        fields = "__all__"
        read_only_fields = ["appointment", "start_time"]
        extra_kwargs = {
            "notes": {"max_length": 1000},
        }

    def validate(self, data):
        start_time = getattr(self.instance, 'start_time', None) or self.context.get('start_time')
        end_time = data.get('end_time')

        if end_time and start_time and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time"})
        return data


class AppointmentCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class UpcomingAppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    doctor_name = serializers.CharField(source="doctor.get_full_name", read_only=True)
    doctor_specialization = serializers.CharField(
        source="doctor.doctor_profile.specialization", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "scheduled_time",
            "duration",
            "reason",
            "status",
            "patient_name",
            "doctor_name",
            "doctor_specialization",
        ]