import os
from celery import Celery
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import VideoRoom


