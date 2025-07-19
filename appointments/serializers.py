from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Appointment, SessionRecord
from accounts.models import User, DoctorProfile


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
            "doctor": {
                "write_only": True,
                "queryset": User.objects.filter(role=User.Role.DOCTOR),
            },
        }

    def validate(self, data):
        if "request" in self.context and not self.context["request"].user.is_patient:
            raise serializers.ValidationError("Only patients can book appointments")
        scheduled_time = data.get("scheduled_time")
        end_time = scheduled_time + timedelta(minutes=data.get("duration", 30))
        doctor = data.get("doctor")

        if (
            doctor.doctor_profile.verification_status
            != DoctorProfile.VerificationStatus.APPROVED
        ):
            raise serializers.ValidationError("Selected doctor is not verified")
        if scheduled_time < timezone.now():
            raise serializers.ValidationError("Cannot book appointment in the past")

        conflicting_appointments = Appointment.objects.filter(
            doctor=doctor,
            scheduled_time__lte=scheduled_time,
            end_time__gte=scheduled_time,
            status=Appointment.AppointmentStatus.SCHEDULED,
        ).exists()

        if conflicting_appointments:
            raise serializers.ValidationError("Doctor is not available at this time")

        overlapping_appointments = Appointment.objects.filter(
            doctor=doctor,
            scheduled_time__lt=end_time,
            status=Appointment.AppointmentStatus.SCHEDULED,
        ).extra(
            where=['DATETIME(scheduled_time, "+" || duration || " minutes") > %s'],
            params=[scheduled_time],
        )

        if self.instance:
            overlapping_appointments = overlapping_appointments.exclude(
                pk=self.instance.pk
            )

        if overlapping_appointments.exists():
            raise serializers.ValidationError(
                "This time slot is unavailable. The doctor has a conflicting appointment."
            )

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
