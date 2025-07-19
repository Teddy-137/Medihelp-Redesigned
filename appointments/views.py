from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Appointment, SessionRecord
from accounts.models import User
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
        return {
            "request": self.request,
        }

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)


class UpcomingAppointmentsView(generics.ListAPIView):
    serializer_class = UpcomingAppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()

        base_queryset = Appointment.objects.filter(
            scheduled_time__gte=now, status=Appointment.AppointmentStatus.SCHEDULED
        )

        if user.is_patient:
            return base_queryset.filter(patient=user).order_by("scheduled_time")

        elif user.is_doctor:
            return base_queryset.filter(doctor=user).order_by("scheduled_time")

        # Admins see all appointments
        return base_queryset


class AppointmentCancelView(generics.UpdateAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        appointment = super().get_object()
        user = self.request.user

        if not (user == appointment.patient or user == appointment.doctor):
            raise PermissionDenied("You are not authorized to cancel this appointment")

        if appointment.status != Appointment.AppointmentStatus.SCHEDULED:
            raise PermissionDenied("You can only cancel scheduled appointments")

        return appointment

    def update(self, request, *args, **kwargs):
        appointment = self.get_object()
        cancel_serializer = AppointmentCancelSerializer(appointment, data=request.data)
        cancel_serializer.is_valid(raise_exception=True)

        reason = cancel_serializer.validated_data.get("reason", "Cancelled by user.")

        appointment.status = Appointment.AppointmentStatus.CANCELLED
        appointment.reason = reason
        appointment.save()

        response_serializer = self.get_serializer(appointment)

        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SessionRecordCreateView(generics.CreateAPIView):
    serializer_class = SessionRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        appointment = get_object_or_404(Appointment, pk=self.kwargs["appointment_id"])

        # This permission check is correct
        if self.request.user != appointment.doctor:
            raise PermissionDenied(
                "Only the assigned doctor can create session records."
            )

        # This check for existing record is also correct and can be kept
        if hasattr(appointment, "session_record"):
            raise ValidationError("Session record already exists for this appointment.")

        if appointment.status != Appointment.AppointmentStatus.SCHEDULED:
            raise ValidationError(
                "Cannot create a session for an appointment that is not scheduled."
            )

        serializer.save(appointment=appointment, start_time=timezone.now())
