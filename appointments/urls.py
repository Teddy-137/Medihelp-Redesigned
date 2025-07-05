from django.urls import path
from .views import (
    AppointmentCreateView,
    UpcomingAppointmentsView,
    AppointmentCancelView,
    SessionRecordCreateView,
)

urlpatterns = [
    path("", AppointmentCreateView.as_view(), name="appointment-create"),
    path(
        "upcoming/",
        UpcomingAppointmentsView.as_view(),
        name="upcoming-appointments",
    ),
    path(
        "<int:pk>/cancel/",
        AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
    path(
        "<int:appointment_id>/session/",
        SessionRecordCreateView.as_view(),
        name="session-record-create",
    ),
]
