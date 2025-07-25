from django.contrib import admin
from .models import Appointment, SessionRecord

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'scheduled_time', 'status')
    list_filter = ('status', 'scheduled_time')
    search_fields = ('patient__first_name', 'patient__last_name', 'doctor__first_name', 'doctor__last_name')

@admin.register(SessionRecord)
class SessionRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'start_time', 'end_time')
    search_fields = ('appointment__id',)