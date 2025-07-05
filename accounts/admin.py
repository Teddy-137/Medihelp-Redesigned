from django.contrib import admin
from .models import PatientProfile, DoctorProfile


admin.site.register(PatientProfile)
admin.site.register(DoctorProfile)