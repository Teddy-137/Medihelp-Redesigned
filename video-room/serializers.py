from rest_framework import serializers
from .models import VideoRoom


class VideoRoomSerializer(serializers.ModelSerializer):
    appointment_id = serializers.IntegerField(source="appointment.id", read_only=True)
    doctor_name = serializers.CharField(
        source="appointment.doctor.get_full_name", read_only=True
    )
    patient_name = serializers.CharField(
        source="appointment.patient.get_full_name", read_only=True
    )

    class Meta:
        model = VideoRoom
        fields = [
            "room_name",
            "room_url",
            "expires_at",
            "is_active",
            "appointment_id",
            "doctor_name",
            "patient_name",
        ]
        read_only_fields = fields
