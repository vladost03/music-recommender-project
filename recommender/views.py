from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

from .forms import UserPreferenceForm
from .models import TrackRecommendation, UserPreference

load_dotenv()

sp_oauth = SpotifyOAuth(
    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI'),
    scope="user-library-read user-read-playback-state user-top-read"
)

def welcome(request):
    return render(request, 'recommender/register.html')

def spotify_login(request):
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

def spotify_callback(request):
    code = request.GET.get('code')
    token_info = sp_oauth.get_access_token(code)
    access_token = token_info['access_token']
    request.session['access_token'] = access_token
    return redirect('preferences')  # перенаправляємо на форму вподобань

def preference_input(request):
    if 'access_token' not in request.session:
        messages.warning(request, "Будь ласка, авторизуйтесь через Spotify.")
        return redirect('spotify-login')

    if request.method == 'POST':
        form = UserPreferenceForm(request.POST)
        if form.is_valid():
            preference = form.save(commit=False)
            preference.user_session_key = request.session.session_key
            preference.save()
            return redirect('recommendations')
    else:
        form = UserPreferenceForm()
    return render(request, 'recommender/preferences.html', {'form': form})

def recommendations(request):
    if 'access_token' not in request.session:
        messages.warning(request, "Будь ласка, авторизуйтесь через Spotify.")
        return redirect('spotify-login')

    access_token = request.session['access_token']
    sp = spotipy.Spotify(auth=access_token)

    # Отримуємо вподобання користувача
    preference = UserPreference.objects.filter(user_session_key=request.session.session_key).last()
    if not preference:
        messages.error(request, "Не знайдено вподобань користувача.")
        return redirect('preferences')

    genre = preference.genre.lower().strip()  # нормалізуємо

    # Отримуємо список доступних жанрів
    try:
        genre_seeds = sp.recommendation_genre_seeds()
        available_genres = genre_seeds['genres']
    except spotipy.exceptions.SpotifyException as e:
        messages.error(request, f"Spotify API error при отриманні жанрів: {e}")
        return redirect('preferences')
    except Exception as e:
        messages.error(request, f"Загальна помилка при отриманні жанрів: {e}")
        return redirect('preferences')

    # Перевірка, чи жанр підтримується
    if genre not in available_genres:
        messages.error(request, f"Жанр '{genre}' не підтримується Spotify.")
        return redirect('preferences')

    # Отримання рекомендацій
    try:
        results = sp.recommendations(seed_genres=[genre], limit=10)
    except spotipy.exceptions.SpotifyException as e:
        messages.error(request, f"Spotify error при отриманні рекомендацій: {e}")
        return redirect('preferences')

    # Зберігання результатів
    TrackRecommendation.objects.filter(user_session_key=request.session.session_key).delete()
    tracks = []
    for track in results['tracks']:
        tracks.append({
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'url': track['external_urls']['spotify']
        })
        TrackRecommendation.objects.create(
            user_session_key=request.session.session_key,
            track_name=track['name'],
            artist_name=track['artists'][0]['name'],
            spotify_url=track['external_urls']['spotify']
        )

    return render(request, 'recommender/recommendations.html', {'tracks': tracks})



@login_required
def recommendations_view(request):
    recommendations = TrackRecommendation.objects.filter(
        user_session_key=request.session.session_key
    ).order_by('-recommended_at')
    return render(request, 'recommender/recommendations.html', {'recommendations': recommendations})
