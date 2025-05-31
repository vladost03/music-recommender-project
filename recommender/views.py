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

# Updated list of valid Spotify genre seeds
VALID_SPOTIFY_GENRES = [
    'acoustic', 'afrobeat', 'alt-rock', 'alternative', 'ambient', 'anime',
    'black-metal', 'bluegrass', 'blues', 'bossanova', 'brazil', 'breakbeat',
    'british', 'cantopop', 'chicago-house', 'children', 'chill', 'classical',
    'club', 'comedy', 'country', 'dance', 'dancehall', 'death-metal',
    'deep-house', 'detroit-techno', 'disco', 'disney', 'drum-and-bass',
    'dub', 'dubstep', 'edm', 'electro', 'electronic', 'emo', 'folk',
    'forro', 'french', 'funk', 'garage', 'german', 'gospel', 'goth',
    'grindcore', 'groove', 'grunge', 'guitar', 'happy', 'hard-rock',
    'hardcore', 'hardstyle', 'heavy-metal', 'hip-hop', 'holidays',
    'honky-tonk', 'house', 'idm', 'indian', 'indie', 'indie-pop',
    'industrial', 'iranian', 'j-dance', 'j-idol', 'j-pop', 'j-rock',
    'jazz', 'k-pop', 'kids', 'latin', 'latino', 'malay', 'mandopop',
    'metal', 'metal-misc', 'metalcore', 'minimal-techno', 'movies',
    'mpb', 'new-age', 'new-release', 'opera', 'pagode', 'party',
    'philippines-opm', 'piano', 'pop', 'pop-film', 'post-dubstep',
    'power-pop', 'progressive-house', 'psych-rock', 'punk', 'punk-rock',
    'r-n-b', 'rainy-day', 'reggae', 'reggaeton', 'road-trip', 'rock',
    'rock-n-roll', 'rockabilly', 'romance', 'sad', 'salsa', 'samba',
    'sertanejo', 'show-tunes', 'singer-songwriter', 'ska', 'sleep',
    'songwriter', 'soul', 'soundtracks', 'spanish', 'study', 'summer',
    'swedish', 'synth-pop', 'tango', 'techno', 'trance', 'trip-hop',
    'turkish', 'work-out', 'world-music'
]

def get_spotify_user_info(request):
    """Helper function to get Spotify user info if available"""
    if 'access_token' not in request.session:
        return None
    
    try:
        access_token = request.session['access_token']
        sp = spotipy.Spotify(auth=access_token)
        user_info = sp.current_user()
        return {
            'spotify_id': user_info.get('id'),
            'display_name': user_info.get('display_name', user_info.get('id')),
            'email': user_info.get('email'),
            'followers': user_info.get('followers', {}).get('total', 0)
        }
    except:
        return None

def welcome(request):
    spotify_user = get_spotify_user_info(request)
    return render(request, 'recommender/register.html', {'spotify_user': spotify_user})

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

    spotify_user = get_spotify_user_info(request)
    
    if request.method == 'POST':
        form = UserPreferenceForm(request.POST)
        if form.is_valid():
            preference = form.save(commit=False)
            preference.user_session_key = request.session.session_key
            preference.save()
            return redirect('generate_recommendations')
    else:
        form = UserPreferenceForm()
    return render(request, 'recommender/preferences.html', {
        'form': form, 
        'spotify_user': spotify_user
    })

def refresh_spotify_token(request):
    """Helper function to refresh Spotify token if needed"""
    try:
        if 'refresh_token' in request.session:
            token_info = sp_oauth.refresh_access_token(request.session['refresh_token'])
            if token_info and 'access_token' in token_info:
                request.session['access_token'] = token_info['access_token']
                if 'refresh_token' in token_info:
                    request.session['refresh_token'] = token_info['refresh_token']
                return token_info['access_token']
    except Exception as e:
        print(f"Token refresh failed: {e}")
    return request.session.get('access_token')

def get_recommendations_with_fallback(sp, genre_list, limit=10):
    """
    Try to get recommendations with multiple fallback strategies
    """
    results = None
    used_genre = None
    
    # Method 1: Try each genre in the list
    for genre in genre_list:
        if genre in VALID_SPOTIFY_GENRES:
            try:
                print(f"Trying recommendations for genre: {genre}")
                # Fixed: Pass seed_genres as a list, not a string
                results = sp.recommendations(seed_genres=[genre], limit=limit)
                if results and results.get('tracks'):
                    print(f"Success! Got {len(results['tracks'])} tracks for {genre}")
                    used_genre = genre
                    break
            except spotipy.exceptions.SpotifyException as e:
                print(f"Failed for genre {genre}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error for genre {genre}: {e}")
                continue
    
    # Method 2: Try client credentials if user auth failed
    if not results:
        try:
            from spotipy.oauth2 import SpotifyClientCredentials
            client_credentials_manager = SpotifyClientCredentials(
                client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
            )
            sp_client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            
            for genre in genre_list:
                if genre in VALID_SPOTIFY_GENRES:
                    try:
                        print(f"Trying client credentials for genre: {genre}")
                        results = sp_client.recommendations(seed_genres=[genre], limit=limit)
                        if results and results.get('tracks'):
                            print(f"Success with client credentials for {genre}!")
                            used_genre = genre
                            break
                    except Exception as e:
                        print(f"Client credentials failed for {genre}: {e}")
                        continue
        except Exception as e:
            print(f"Client credentials setup failed: {e}")
    
    return results, used_genre

def recommendations(request):
    if 'access_token' not in request.session:
        messages.warning(request, "Будь ласка, авторизуйтесь через Spotify.")
        return redirect('spotify-login')

    # Refresh token if needed
    access_token = refresh_spotify_token(request)
    if not access_token:
        messages.error(request, "Session expired. Please log in again.")
        return redirect('spotify-login')
    
    sp = spotipy.Spotify(auth=access_token)
    
    # Test authentication
    try:
        user_info = sp.current_user()
        print(f"User authenticated: {user_info['id']}")
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 401:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('spotify-login')
        else:
            print(f"Authentication error: {e}")
            messages.error(request, "Authentication error. Please try logging in again.")
            return redirect('spotify-login')

    spotify_user = get_spotify_user_info(request)

    # Get user preferences
    preference = UserPreference.objects.filter(user_session_key=request.session.session_key).last()
    if not preference:
        messages.error(request, "Не знайдено вподобань користувача.")
        return redirect('preferences')

    genre = preference.genre.lower().strip()
    
    # Map user-friendly genres to Spotify genres with priorities
    genre_mapping = {
        'rock': ['rock', 'alt-rock', 'indie', 'hard-rock', 'grunge'],
        'pop': ['pop', 'indie-pop', 'synth-pop', 'pop-film', 'power-pop'],
        'jazz': ['jazz', 'blues', 'soul', 'funk'],
        'hip-hop': ['hip-hop', 'r-n-b', 'funk', 'soul'],
        'classical': ['classical', 'opera', 'piano', 'instrumental'],
        'electronic': ['electronic', 'edm', 'house', 'techno', 'ambient', 'electro'],
        'reggae': ['reggae', 'reggaeton', 'dub', 'ska'],
        'metal': ['metal', 'heavy-metal', 'black-metal', 'death-metal', 'metalcore', 'hard-rock'],
        'blues': ['blues', 'jazz', 'soul', 'funk', 'r-n-b'],
        'country': ['country', 'folk', 'bluegrass', 'honky-tonk', 'rockabilly']
    }
    
    # Get possible genres for the selected genre
    possible_genres = genre_mapping.get(genre, [genre])
    
    # Get recommendations with fallback
    results, used_genre = get_recommendations_with_fallback(sp, possible_genres, limit=10)
    
    # Final fallback - search for popular tracks
    if not results:
        try:
            search_query = f"genre:{genre}" if genre in ['rock', 'pop', 'jazz', 'metal', 'blues', 'country'] else 'popular music'
            print(f"Using search fallback with query: {search_query}")
            search_results = sp.search(q=search_query, type='track', limit=10)
            if search_results['tracks']['items']:
                results = {'tracks': search_results['tracks']['items']}
                messages.info(request, f"Показуємо популярні треки жанру '{genre}' замість персональних рекомендацій")
                print("Using search results as fallback")
        except Exception as e:
            print(f"Search fallback failed: {e}")
            
    # Absolute last resort
    if not results:
        try:
            search_results = sp.search(q='popular', type='track', limit=10)
            if search_results['tracks']['items']:
                results = {'tracks': search_results['tracks']['items']}
                messages.warning(request, "Не вдалося знайти рекомендації для вашого жанру. Показуємо популярні треки.")
        except:
            messages.error(request, "Не вдалося отримати рекомендації. Спробуйте пізніше.")
            return redirect('preferences')

    if not results or not results.get('tracks'):
        messages.error(request, "Не вдалося знайти треки. Спробуйте інший жанр або пізніше.")
        return redirect('preferences')

    # Clear previous recommendations and save new ones
    TrackRecommendation.objects.filter(user_session_key=request.session.session_key).delete()
    tracks = []
    
    for track in results['tracks']:
        track_data = {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'url': track['external_urls']['spotify']
        }
        tracks.append(track_data)
        
        TrackRecommendation.objects.create(
            user_session_key=request.session.session_key,
            track_name=track['name'],
            artist_name=track['artists'][0]['name'],
            spotify_url=track['external_urls']['spotify']
        )

    # Add success message if we used the exact genre requested
    if used_genre and used_genre == genre:
        messages.success(request, f"Знайдено рекомендації для жанру '{genre}'!")
    elif used_genre:
        messages.info(request, f"Використано схожий жанр '{used_genre}' для жанру '{genre}'")

    return render(request, 'recommender/recommendations.html', {
        'tracks': tracks,
        'spotify_user': spotify_user
    })

def recommendations_view(request):
    recommendations = TrackRecommendation.objects.filter(
        user_session_key=request.session.session_key
    ).order_by('-recommended_at')
    spotify_user = get_spotify_user_info(request)
    return render(request, 'recommender/recommendations.html', {
        'recommendations': recommendations,
        'spotify_user': spotify_user
    })

def spotify_logout(request):
    """Clear Spotify session data"""
    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    messages.success(request, "Ви вийшли з Spotify.")
    return redirect('welcome')