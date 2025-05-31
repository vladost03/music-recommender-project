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

    # SOLUTION 1: Use a predefined list of common Spotify genres
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

    # SOLUTION 2: Alternative approach - try to get available genres with better error handling
    # You can uncomment this if you want to try the original API call with better error handling
    """
    try:
        # Try different methods to get available genres
        try:
            # Method 1: Original approach
            genre_seeds = sp.recommendation_genre_seeds()
            available_genres = genre_seeds['genres']
        except:
            # Method 2: Try making a direct request
            import requests
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get('https://api.spotify.com/v1/recommendations/available-genre-seeds', headers=headers)
            if response.status_code == 200:
                available_genres = response.json()['genres']
            else:
                # Fallback to common genres
                available_genres = common_spotify_genres
    except Exception as e:
        messages.error(request, f"Помилка при отриmanні жанрів: {e}")
        available_genres = common_spotify_genres

    if genre not in available_genres:
        messages.error(request, f"Жанр '{genre}' не підтримується Spotify.")
        return redirect('preferences')
    """

    # Get recommendations with simpler approach first
    try:
        # Method 1: Try the simplest recommendations call first
        print(f"Trying recommendations for genre: {final_genre}")  # Debug line
        results = sp.recommendations(seed_genres=[final_genre], limit=10)
        print(f"Success! Got {len(results['tracks'])} tracks")  # Debug line
        
    except spotipy.exceptions.SpotifyException as e:
        print(f"Method 1 failed with status {e.http_status}: {e}")  # Debug line
        
        # Method 2: Try alternative rock genres if original rock failed
        if final_genre == 'rock':
            alternative_genres = ['alt-rock', 'rock-n-roll', 'classic-rock', 'indie-rock', 'hard-rock']
            for alt_genre in alternative_genres:
                try:
                    print(f"Trying alternative genre: {alt_genre}")
                    results = sp.recommendations(seed_genres=[alt_genre], limit=10)
                    print(f"Success with {alt_genre}!")
                    final_genre = alt_genre  # Update for display
                    break
                except:
                    continue
            else:
                # If all rock alternatives fail, try Client Credentials
                try:
                    from spotipy.oauth2 import SpotifyClientCredentials
                    client_credentials_manager = SpotifyClientCredentials(
                        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
                    )
                    sp_client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                    results = sp_client.recommendations(seed_genres=['rock'], limit=10)
                    print("Success with client credentials!")  # Debug line
                    
                except Exception as e2:
                    # Method 3: Try search-based approach as last resort
                    try:
                        search_results = sp.search(q='rock', type='track', limit=10)
                        if search_results['tracks']['items']:
                            # Convert search results to recommendation format
                            results = {'tracks': search_results['tracks']['items']}
                            messages.info(request, "Показуємо популярні рок треки замість персональних рекомендацій")
                            print("Using search results as fallback")
                        else:
                            raise Exception("No search results found")
                    except Exception as e3:
                        messages.error(request, f"Не вдалося отримати рекомендації для жанру 'rock'. Спробуйте жанри: pop, jazz, electronic, hip-hop")
                        return redirect('preferences')
        else:
            # For non-rock genres, try client credentials
            try:
                from spotipy.oauth2 import SpotifyClientCredentials
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
                )
                sp_client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                results = sp_client.recommendations(seed_genres=[final_genre], limit=10)
                print("Success with client credentials!")  # Debug line
                
            except Exception as e2:
                print(f"All methods failed: {e2}")  # Debug line
                if e.http_status == 401:
                    messages.error(request, "Session expired. Please log in again.")
                    return redirect('spotify-login')
                else:
                    messages.error(request, f"Рекомендації недоступні для жанру '{final_genre}'. Спробуйте: pop, jazz, electronic, hip-hop")
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