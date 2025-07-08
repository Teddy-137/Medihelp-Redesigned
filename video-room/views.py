from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied
from .models import VideoRoom
from .serializers import VideoRoomSerializer
from .services import DailyService
from appointments.models import Appointment
from datetime import timedelta
import uuid


class VideoRoomCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            raise NotFound("Appointment not found")

        user = request.user
        if user not in [appointment.patient, appointment.doctor]:
            raise PermissionDenied(
                "You don't have permission to create a room for this appointment"
            )

        if hasattr(appointment, "video_room"):
            return Response(
                {
                    "message": "Room already exists",
                    "room": VideoRoomSerializer(appointment.video_room).data,
                },
                status=status.HTTP_200_OK,
            )

        room_name = f"telemed-{appointment.id}-{uuid.uuid4().hex[:6]}"
        room_data = DailyService.create_room(
            room_name=room_name,
            expiration=int(
                (appointment.scheduled_time + timedelta(hours=1)).timestamp()
            ),
        )

        video_room = VideoRoom.objects.create(
            appointment=appointment,
            room_name=room_name,
            room_url=room_data["url"],
            expires_at=appointment.scheduled_time + timedelta(hours=1),
        )

        return Response(
            VideoRoomSerializer(video_room).data, status=status.HTTP_201_CREATED
        )



class VideoRoomDetailView(generics.RetrieveAPIView):
    serializer_class = VideoRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "room_name"
    lookup_url_kwarg = "room_name"

    def get_queryset(self):
        return VideoRoom.objects.filter(is_active=True)

    def get_object(self):
        room = super().get_object()
        user = self.request.user
        if user not in [room.appointment.patient, room.appointment.doctor]:
            raise PermissionDenied("You don't have permission to view this room")
        return room
    