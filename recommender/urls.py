from django.urls import path
from . import views

urlpatterns = [
    path('spotify/login/', views.spotify_login, name='spotify-login'),
    path('spotify/callback/', views.spotify_callback, name='spotify-callback'),
    path('preferences/', views.preference_input, name='preferences'),
    path('recommendations/', views.recommendations, name='recommendations'),
]