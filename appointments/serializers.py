from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Appointment, SessionRecord
from accounts.models import DoctorProfile


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    doctor_name = serializers.CharField(source="doctor.get_full_name", read_only=True)
    doctor_specialization = serializers.CharField(
        source="doctor.doctor_profile.specialization", read_only=True
    )

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
            "patient": {"read_only": True},
            "status": {"read_only": True},
        }

    def validate(self, data):
        if not self.context["request"].user.is_patient:
            raise serializers.ValidationError("Only patients can book appointments")

        doctor = data.get("doctor")

        if (
            doctor.doctor_profile.verification_status
            != DoctorProfile.VerificationStatus.APPROVED
        ):
            raise serializers.ValidationError("Doctor is not approved")

        if data["scheduled_time"] < timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future")

        conflicting_appointments = Appointment.objects.filter(
            doctor=data["doctor"],
            scheduled_time__lte=data["scheduled_time"],
            status=Appointment.AppointmentStatus.SCHEDULED,
        ).exists()

        if conflicting_appointments:
            raise serializers.ValidationError("Doctor is not available at this time")

        return data


class SessionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRecord
        fields = "__all__"
        read_only_fields = ["appointment", "start_time"]

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
