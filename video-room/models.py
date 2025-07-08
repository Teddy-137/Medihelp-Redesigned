from django.db import models
from django.conf import settings
from appointments.models import Appointment
from datetime import timedelta
import uuid

class VideoRoom(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='video_room'
    )
    room_name = models.CharField(max_length=100, unique=True)
    room_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Room for Appointment #{self.appointment.id}"
    
    @classmethod
    def create_for_appointment(cls, appointment):
        room_name = f"telemed-{appointment.id}-{uuid.uuid4().hex[:6]}"
        expires_at = appointment.scheduled_time + timedelta(hours=1)
        
        return cls.objects.create(
            appointment=appointment,
            room_name=room_name,
            room_url=f"{settings.FRONTEND_URL}/room/{room_name}",
            expires_at=expires_at
        )