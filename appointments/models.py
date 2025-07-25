from datetime import timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import User


class Appointment(models.Model):
    class AppointmentStatus(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NOSHOW = "NOSHOW", "No Show"

    # Valid status transitions
    ALLOWED_TRANSITIONS = {
        AppointmentStatus.SCHEDULED: [
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NOSHOW
        ],
        AppointmentStatus.COMPLETED: [],
        AppointmentStatus.CANCELLED: [],
        AppointmentStatus.NOSHOW: [],
    }

    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="patient_appointments"
    )
    doctor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="doctor_appointments"
    )
    scheduled_time = models.DateTimeField()
    duration = models.PositiveIntegerField(default=30)
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
    
    def clean(self):
        super().clean()
        if self.status == self.AppointmentStatus.SCHEDULED and self.scheduled_time < timezone.now():
            raise ValidationError({"scheduled_time": "Cannot schedule an appointment in the past."})

        # Validate status transitions if this is an existing instance
        if self.pk:
            try:
                original = Appointment.objects.get(pk=self.pk)
                if original.status != self.status:
                    allowed_next_statuses = self.ALLOWED_TRANSITIONS.get(original.status, [])
                    if self.status not in allowed_next_statuses:
                        raise ValidationError(
                            {
                                "status": f"Invalid status transition from {original.status} to {self.status}...",
                                "allowed_transitions": ', '.join(allowed_next_statuses) or 'none'
                            }
                        )
            except Appointment.DoesNotExist:
                pass 

    def save(self, *args, **kwargs):
        self.full_clean()  
        super().save(*args, **kwargs)

    def __str__(self):
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
    diagnosis = models.TextField() 
    treatment = models.TextField()

    def clean(self):
        super().clean()
        if not self.diagnosis:
            raise ValidationError({"diagnosis": "Diagnosis is required"})
        if not self.treatment:
            raise ValidationError({"treatment": "Treatment is required"})
        # Validate end_time is after start_time if both are provided
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})
        if self.appointment and self.appointment.status != Appointment.AppointmentStatus.COMPLETED:
            raise ValidationError({"appointment": "Can only create session records for completed appointments"})

        
    def save(self, *args, **kwargs):
        if not self.pk and SessionRecord.objects.filter(appointment=self.appointment).exists():
            raise ValidationError("Session record already exists for this appointment")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Session for Appointment #{self.appointment.id}"
    class Meta:
        ordering = ['-start_time']
