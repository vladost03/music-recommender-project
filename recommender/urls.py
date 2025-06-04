from django.urls import path
from . import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('spotify/login/', views.spotify_login, name='spotify-login'),
    path('spotify/callback/', views.spotify_callback, name='spotify-callback'),
    path('spotify/logout/', views.spotify_logout, name='spotify-logout'),
    path('get-user-top-stats/', views.get_user_top_stats, name='get-user-top-stats'),
    path('preferences/', views.preference_input, name='preferences'),
    path('recommendations/', views.recommendations, name='generate_recommendations'),
    path('recommendations/view/', views.recommendations_view, name='recommendations-view'),
]