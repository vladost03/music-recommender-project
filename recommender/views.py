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
    scope="user-library-read user-read-playback-state user-top-read user-read-recently-played"
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
    return redirect('preferences')

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

    genre = preference.genre.lower().strip()

    # Use a predefined list of common Spotify genres
    # This avoids the API call that's causing the 404 error
    common_spotify_genres = [
        'acoustic', 'afrobeat', 'alt-rock', 'alternative', 'ambient', 'ancient',
        'anime', 'anti-folk', 'antiviral-pop', 'arabic', 'argentine', 'artcore',
        'atmospheric', 'australian', 'avant-garde', 'avantgarde', 'axé', 'baladas',
        'ballad', 'bass', 'beats', 'bebop', 'bhangra', 'big-band', 'black-metal',
        'bluegrass', 'blues', 'bossa-nova', 'brazil', 'breakbeat', 'british',
        'broken-beat', 'celtic', 'chamber-pop', 'chicago-house', 'chill',
        'chillout', 'chiptune', 'choir', 'christian', 'christmas', 'classical',
        'club', 'comedy', 'country', 'dance', 'dancehall', 'death-metal',
        'deep-house', 'detroit-techno', 'disco', 'disney', 'drum-and-bass',
        'dub', 'dubstep', 'edm', 'electronic', 'emo', 'folk', 'funk', 'garage',
        'gospel', 'goth', 'grunge', 'guitar', 'happy', 'hardcore', 'hip-hop',
        'house', 'idm', 'indian', 'indie', 'indie-pop', 'industrial', 'iranian',
        'j-dance', 'j-idol', 'j-pop', 'j-rock', 'jazz', 'k-pop', 'kids',
        'latin', 'latino', 'metal', 'metalcore', 'minimal-techno', 'movies',
        'mpb', 'new-age', 'new-release', 'opera', 'pagode', 'party', 'piano',
        'pop', 'pop-film', 'post-dubstep', 'power-pop', 'progressive-house',
        'psych-rock', 'punk', 'punk-rock', 'r-n-b', 'rainy-day', 'reggae',
        'reggaeton', 'rock', 'rock-n-roll', 'rockabilly', 'romance', 'sad',
        'salsa', 'samba', 'sertanejo', 'show-tunes', 'singer-songwriter',
        'ska', 'sleep', 'songwriter', 'soul', 'soundtracks', 'spanish',
        'study', 'summer', 'swedish', 'synth-pop', 'tango', 'techno',
        'trance', 'trip-hop', 'turkish', 'work-out', 'world-music'
    ]

    # Check if genre is in our predefined list
    if genre not in common_spotify_genres:
        # Try to find a close match or suggest alternatives
        similar_genres = [g for g in common_spotify_genres if genre in g or g in genre]
        if similar_genres:
            messages.warning(request, f"Жанр '{genre}' не знайдено. Спробуйте один з цих: {', '.join(similar_genres[:5])}")
        else:
            messages.error(request, f"Жанр '{genre}' не підтримується. Доступні жанри: pop, rock, jazz, electronic, hip-hop, classical, та інші.")
        return redirect('preferences')

    # Get recommendations with better error handling and debugging
    try:
        # First, let's try to get user's top tracks to use as seed tracks
        # This might work better than just using genre seeds
        try:
            top_tracks = sp.current_user_top_tracks(limit=5, time_range='medium_term')
            if top_tracks['items']:
                # Use a combination of seed tracks and genre
                seed_tracks = [track['id'] for track in top_tracks['items'][:2]]
                results = sp.recommendations(
                    seed_tracks=seed_tracks,
                    seed_genres=[genre],
                    limit=10
                )
            else:
                # Fallback to genre-only recommendations
                results = sp.recommendations(seed_genres=[genre], limit=10)
        except:
            # If top tracks fail, try with popular artists from the genre
            # Search for popular tracks in the genre first
            search_results = sp.search(q=f'genre:{genre}', type='track', limit=5)
            if search_results['tracks']['items']:
                # Use artist seeds instead
                seed_artists = list(set([track['artists'][0]['id'] for track in search_results['tracks']['items'][:2]]))
                results = sp.recommendations(
                    seed_artists=seed_artists,
                    seed_genres=[genre],
                    limit=10
                )
            else:
                # Last fallback - just genre
                results = sp.recommendations(seed_genres=[genre], limit=10)
                
    except spotipy.exceptions.SpotifyException as e:
        # More detailed error handling
        if e.http_status == 404:
            messages.error(request, f"Spotify API endpoint not found. This might be a temporary issue. Please try again later.")
        elif e.http_status == 401:
            messages.error(request, "Authorization expired. Please log in again.")
            return redirect('spotify-login')
        elif e.http_status == 403:
            messages.error(request, "Access forbidden. Check your Spotify app permissions.")
        else:
            messages.error(request, f"Spotify API error: {e}")
        return redirect('preferences')
    except Exception as e:
        messages.error(request, f"Загальна помилка при отриманні рекомендацій: {e}")
        return redirect('preferences')

    # Clear previous recommendations and save new ones
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