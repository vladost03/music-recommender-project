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
    if not code:
        messages.error(request, "Authorization failed. Please try again.")
        return redirect('spotify-login')
        
    try:
        token_info = sp_oauth.get_access_token(code)
        access_token = token_info['access_token']
        request.session['access_token'] = access_token
        
        # Store refresh token if available
        if 'refresh_token' in token_info:
            request.session['refresh_token'] = token_info['refresh_token']
            
        print(f"Token obtained successfully")  # Debug line
        return redirect('preferences')
    except Exception as e:
        print(f"Token error: {e}")  # Debug line
        messages.error(request, "Failed to get access token. Please try again.")
        return redirect('spotify-login')

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
    
    # Try to refresh token if it's expired
    try:
        token_info = sp_oauth.refresh_access_token(request.session.get('refresh_token'))
        if token_info:
            access_token = token_info['access_token']
            request.session['access_token'] = access_token
            if 'refresh_token' in token_info:
                request.session['refresh_token'] = token_info['refresh_token']
    except:
        pass  # Continue with existing token
    
    sp = spotipy.Spotify(auth=access_token)
    
    # Test if the token works by trying a simple API call
    try:
        user_info = sp.current_user()
        print(f"User authenticated: {user_info['id']}")  # Debug line
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 401:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('spotify-login')
        else:
            messages.error(request, f"Authentication error: {e}")
            return redirect('spotify-login')

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

    # Get recommendations with simpler approach first
    try:
        # Method 1: Try the simplest recommendations call first
        print(f"Trying recommendations for genre: {genre}")  # Debug line
        results = sp.recommendations(seed_genres=[genre], limit=10)
        print(f"Success! Got {len(results['tracks'])} tracks")  # Debug line
        
    except spotipy.exceptions.SpotifyException as e:
        print(f"Method 1 failed with status {e.http_status}: {e}")  # Debug line
        
        # Method 2: Try using Client Credentials as fallback
        try:
            from spotipy.oauth2 import SpotifyClientCredentials
            client_credentials_manager = SpotifyClientCredentials(
                client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
            )
            sp_client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            results = sp_client.recommendations(seed_genres=[genre], limit=10)
            print("Success with client credentials!")  # Debug line
            
        except spotipy.exceptions.SpotifyException as e2:
            print(f"Method 2 also failed: {e2}")  # Debug line
            
            # Method 3: Try with different parameters
            try:
                # Sometimes the API works better with additional parameters
                results = sp.recommendations(
                    seed_genres=[genre],
                    limit=10,
                    target_energy=0.5,
                    target_danceability=0.5
                )
                print("Success with additional parameters!")  # Debug line
            except Exception as e3:
                print(f"All methods failed: {e3}")  # Debug line
                if e.http_status == 404:
                    messages.error(request, f"Рекомендації недоступні для жанру '{genre}'. Спробуйте інший жанр.")
                elif e.http_status == 401:
                    messages.error(request, "Session expired. Please log in again.")
                    return redirect('spotify-login')
                else:
                    messages.error(request, f"Помилка Spotify API: {e}")
                return redirect('preferences')
                
    except Exception as e:
        print(f"General error: {e}")  # Debug line
        messages.error(request, f"Загальна помилка: {e}")
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