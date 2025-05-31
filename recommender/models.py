from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorite_genres = models.CharField(max_length=255, blank=True)
    favorite_artists = models.CharField(max_length=255, blank=True)
    mood = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f'Profile of {self.user.username}'


class TrackRecommendation(models.Model):
    track_name = models.CharField(max_length=255)
    artist_name = models.CharField(max_length=255)
    spotify_url = models.URLField()
    user_session_key = models.CharField(max_length=255)
    recommended_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.track_name} by {self.artist_name}'

class UserPreference(models.Model):
    user_session_key = models.CharField(max_length=255, null=True, blank=True) # Унікальний ключ сесії
    genre = models.CharField(max_length=50)
    
    def __str__(self):
        return f"Preference ({self.genre})"
    

