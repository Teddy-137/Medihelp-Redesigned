from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Appointment, SessionRecord
from accounts.models import User  # Ensure User is imported
from .serializers import (
    AppointmentSerializer,
    SessionRecordSerializer,
    AppointmentCancelSerializer,
    UpcomingAppointmentSerializer,
)

class AppointmentCreateView(generics.CreateAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_serializer_context(self):
        # Ensure serializer has access to request
        return {"request": self.request}
    
    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)


class UpcomingAppointmentsView(generics.ListAPIView):
    serializer_class = UpcomingAppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        base_queryset = Appointment.objects.filter(
            scheduled_time__gte=now, 
            status=Appointment.AppointmentStatus.SCHEDULED
        )
        if user.is_patient:
            return base_queryset.filter(patient=user).order_by("scheduled_time")
        elif user.is_doctor:
            return base_queryset.filter(doctor=user).order_by("scheduled_time")
        else:
            # Admins and other roles see all upcoming appointments
            return base_queryset.order_by("scheduled_time")

class AppointmentCancelView(generics.UpdateAPIView):
    serializer_class = AppointmentCancelSerializer
    queryset = Appointment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        appointment = super().get_object()
        user = self.request.user
        if not (user == appointment.patient or user == appointment.doctor or user.is_admin):
            raise PermissionDenied("You are not authorized to cancel this appointment.")
        
        # Ensure appointment is scheduled before allowing cancel
        if appointment.status != Appointment.AppointmentStatus.SCHEDULED:
            raise PermissionDenied("Only scheduled appointments can be cancelled.")
        return appointment
    
    def update(self, request, *args, **kwargs):
        appointment = self.get_object()
        cancel_serializer = self.get_serializer(data=request.data)
        cancel_serializer.is_valid(raise_exception=True)
        reason = cancel_serializer.validated_data.get("reason", "Cancelled by user.")

        appointment.status = Appointment.AppointmentStatus.CANCELLED
        appointment.reason = reason
        appointment.save()

        # Return full appointment data after cancel
        appointment_serializer = AppointmentSerializer(appointment, context={"request": request})
        return Response(appointment_serializer.data, status=status.HTTP_200_OK)

class SessionRecordCreateView(generics.CreateAPIView):
    serializer_class = SessionRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        appointment_pk = self.kwargs.get("appointment_id")
        appointment = get_object_or_404(Appointment, pk=appointment_pk)

        # Check appointment doctor assigned
        if not appointment.doctor:
            raise ValidationError({"detail": "This appointment has no doctor assigned."})

        # Only the assigned doctor can create session records
        if self.request.user != appointment.doctor:
            raise PermissionDenied("Only the assigned doctor can create session records.")

        # Prevent creating duplicate session records
        if hasattr(appointment, "session_record"):
            raise ValidationError({"detail": "A session record already exists for this appointment."})
        
        # Only allow session creation for scheduled appointments
        if appointment.status != Appointment.AppointmentStatus.COMPLETED:
            raise ValidationError({"detail": "Can only create session record for completed appointments."})

        # Save the session record with appointment and start_time
        serializer.save(appointment=appointment, start_time=timezone.now())
