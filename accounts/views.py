from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied
from .models import User, PatientProfile, DoctorProfile
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import (
    UserSerializer,
    PatientProfileSerializer,
    DoctorProfileSerializer,
    PatientRegistrationSerializer,
    DoctorRegistrationSerializer,
    DoctorPublicSerializer,
)


class PatientRegistrationView(generics.CreateAPIView):
    serializer_class = PatientRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Patient registered successfully",
                "user_id": user.id,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class DoctorRegistrationView(generics.CreateAPIView):
    serializer_class = DoctorRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Doctor registered successfully. Account pending verification.",
                "user_id": user.id,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class PatientProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        if not self.request.user.is_patient:
            raise PermissionDenied("Only patients can access this profile")
        return self.request.user.patient_profile


class DoctorProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        if not self.request.user.is_doctor:
            raise PermissionDenied("Only doctors can access this profile")
        return self.request.user.doctor_profile


class DoctorVerificationView(generics.UpdateAPIView):
    queryset = DoctorProfile.objects.all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = "id"

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_status = request.data.get("verification_status")

        if new_status not in [
            choice[0] for choice in DoctorProfile.VerificationStatus.choices
        ]:
            return Response(
                {"error": "Invalid verification status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.verification_status = new_status
        instance.save()

        if new_status == "approved":
            pass

        return Response(
            {
                "message": f"Doctor verification status updated to {new_status}",
                "doctor_id": instance.user.id,
                "status": new_status,
            }
        )


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"


class DoctorListView(generics.ListAPIView):
    queryset = DoctorProfile.objects.filter(verification_status="approved")
    serializer_class = DoctorPublicSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["specialization"]
    search_fields = ["user__first_name", "user__last_name"]
    ordering_fields = ["consultation_fee"]


class DoctorDetailView(generics.RetrieveAPIView):
    queryset = DoctorProfile.objects.filter(verification_status="approved")
    serializer_class = DoctorPublicSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_object(self):
        obj = super().get_object()
        if not obj:
            raise PermissionDenied("Doctor profile not found or not approved")
        return obj
