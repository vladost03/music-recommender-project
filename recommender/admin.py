from django.contrib import admin
from .models import UserProfile, TrackRecommendation, UserPreference

admin.site.register(UserProfile)
admin.site.register(TrackRecommendation)
admin.site.register(UserPreference)
