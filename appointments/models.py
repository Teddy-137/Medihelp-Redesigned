from django.db import models
from accounts.models import User
from django.utils import timezone
from datetime import timedelta


class Appointment(models.Model):
    class AppointmentStatus(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="patient_appointments"
    )
    doctor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="doctor_appointments"
    )
    scheduled_time = models.DateTimeField()
    duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
    )
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_time"]
        indexes = [
            models.Index(fields=["scheduled_time"]),
            models.Index(fields=["status"]),
        ]

    @property
    def end_time(self):
        return self.scheduled_time + timedelta(minutes=self.duration)

    def __str__(self) -> str:
        return (
            f"Appointment #{self.id}: {self.patient.get_full_name()} "
            f"with {self.doctor.get_full_name()} at {self.scheduled_time}"
        )


class SessionRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name="session_record"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    prescription = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if (
            not self.pk
            and SessionRecord.objects.filter(appointment=self.appointment).exists()
        ):
            from django.core.exceptions import ValidationError

            raise ValidationError("Session record already exists for this appointment")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Session for Appointment #{self.appointment.id}"
