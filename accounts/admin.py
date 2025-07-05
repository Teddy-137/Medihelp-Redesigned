from django.contrib import admin
from .models import PatientProfile, DoctorProfile, User

admin.site.register(User)
admin.site.register(PatientProfile)
admin.site.register(DoctorProfile)