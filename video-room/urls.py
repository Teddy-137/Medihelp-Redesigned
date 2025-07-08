from django.urls import path
from .views import VideoRoomCreateView, VideoRoomDetailView

urlpatterns = [
    path(
        "appointment/<int:appointment_id>/",
        VideoRoomCreateView.as_view(),
        name="video-room-create",
    ),
    path(
        "<str:room_name>/",
        VideoRoomDetailView.as_view(),
        name="video-room-detail",
    ),
]
