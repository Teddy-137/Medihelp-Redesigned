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

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)


class UpcomingAppointmentsView(generics.ListAPIView):
    serializer_class = UpcomingAppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()

        if user.is_patient:
            return Appointment.objects.filter(
                patient=user, scheduled_time__gte=now, status="scheduled"
            ).order_by("scheduled_time")

        elif user.is_doctor:
            return Appointment.objects.filter(
                doctor=user, scheduled_time__gte=now, status="scheduled"
            ).order_by("scheduled_time")

        # Admins see all appointments
        return Appointment.objects.filter(
            scheduled_time__gte=now, status="scheduled"
        ).order_by("scheduled_time")


class AppointmentCancelView(generics.UpdateAPIView):
    queryset = Appointment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return AppointmentCancelSerializer

    def get_object(self):
        appointment = get_object_or_404(Appointment, id=self.kwargs["pk"])

        if not (
            self.request.user.is_patient == appointment.patient
            or self.request.user.is_doctor == appointment.doctor
            or self.request.user.is_admin
        ):
            raise PermissionDenied("You are not authorized to cancel this appointment")

        return appointment

    def update(self, request, *args, **kwargs):
        appointment = self.get_object()
        serializer = self.get_serializer(appointment, data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment.status = "cancelled"
        if serializer.validated_data.get("reason"):
            appointment.reason = serializer.validated_data.get("reason")
        appointment.save()
        return Response(
            {
                "message": "Appointment cancelled successfully",
            },
            status=status.HTTP_200_OK,
        )


class SessionRecordCreateView(generics.CreateAPIView):
    serializer_class = SessionRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        appointment = get_object_or_404(
            Appointment, 
            pk=self.kwargs['appointment_id']
        )
        
        if self.request.user != appointment.doctor:
            raise PermissionDenied(
                "Only the assigned doctor can create session records"
            )
        
        if hasattr(appointment, "session_record"):
            raise ValidationError(
                "Session record already exists for this appointment"
            )
        
        serializer.save(appointment=appointment, start_time=timezone.now())
