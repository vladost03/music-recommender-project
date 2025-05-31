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
            return redirect('recommendations')
    else:
        form = UserPreferenceForm()
    return render(request, 'recommender/preferences.html', {
        'form': form, 
        'spotify_user': spotify_user
    })

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

    spotify_user = get_spotify_user_info(request)

    # Отримуємо вподобання користувача
    preference = UserPreference.objects.filter(user_session_key=request.session.session_key).last()
    if not preference:
        messages.error(request, "Не знайдено вподобань користувача.")
        return redirect('preferences')

    genre = preference.genre.lower().strip()
    
    # Map user-friendly genres to Spotify genres with alternatives
    genre_mapping = {
        'rock': ['rock', 'alt-rock', 'indie-rock', 'classic-rock'],
        'pop': ['pop', 'indie-pop', 'synth-pop', 'pop-film'],
        'jazz': ['jazz', 'smooth-jazz', 'bebop', 'swing'],
        'hip-hop': ['hip-hop', 'rap', 'trap', 'old-school'],
        'classical': ['classical', 'opera', 'piano', 'orchestral'],
        'electronic': ['electronic', 'edm', 'house', 'techno', 'ambient'],
        'reggae': ['reggae', 'reggaeton', 'dub', 'ska'],
        'metal': ['metal', 'black-metal', 'death-metal', 'metalcore', 'heavy-metal'],
        'blues': ['blues', 'country-blues', 'electric-blues', 'acoustic-blues'],
        'country': ['country', 'folk', 'bluegrass', 'americana']
    }
    
    # Get list of possible genres for the selected genre
    possible_genres = genre_mapping.get(genre, [genre])
    final_genre = possible_genres[0]  # Start with the first option

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

    # Check if any of the possible genres are in our predefined list
    valid_genres = [g for g in possible_genres if g in common_spotify_genres]
    if not valid_genres:
        # Try to find a close match or suggest alternatives
        similar_genres = []
        for possible_genre in possible_genres:
            similar_genres.extend([g for g in common_spotify_genres if possible_genre in g or g in possible_genre])
        
        if similar_genres:
            final_genre = similar_genres[0]  # Use the first similar genre found
            messages.info(request, f"Використовуємо схожий жанр '{final_genre}' замість '{genre}'")
        else:
            messages.error(request, f"Жанр '{genre}' не підтримується. Доступні жанри: pop, rock, jazz, electronic, hip-hop, classical, та інші.")
            return redirect('preferences')
    else:
        final_genre = valid_genres[0]  # Use the first valid genre

    # Get recommendations with multiple fallback strategies
    results = None
    
    try:
        # Method 1: Try the primary genre
        print(f"Trying recommendations for genre: {final_genre}")
        results = sp.recommendations(seed_genres=[final_genre], limit=10)
        print(f"Success! Got {len(results['tracks'])} tracks")
        
    except spotipy.exceptions.SpotifyException as e:
        print(f"Method 1 failed with status {e.http_status}: {e}")
        
        # Method 2: Try alternative genres for the selected category
        for alt_genre in possible_genres[1:]:  # Skip the first one we already tried
            try:
                print(f"Trying alternative genre: {alt_genre}")
                results = sp.recommendations(seed_genres=[alt_genre], limit=10)
                print(f"Success with {alt_genre}!")
                final_genre = alt_genre
                break
            except:
                continue
        
        # Method 3: Try Client Credentials if user auth failed
        if not results:
            try:
                from spotipy.oauth2 import SpotifyClientCredentials
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
                )
                sp_client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                
                # Try each possible genre with client credentials
                for attempt_genre in possible_genres:
                    try:
                        results = sp_client.recommendations(seed_genres=[attempt_genre], limit=10)
                        final_genre = attempt_genre
                        print(f"Success with client credentials using {attempt_genre}!")
                        break
                    except:
                        continue
                        
            except Exception as e2:
                print(f"Client credentials failed: {e2}")
        
        # Method 4: Search-based fallback
        if not results:
            try:
                search_query = genre if genre in ['rock', 'pop', 'jazz', 'metal', 'blues'] else 'popular music'
                search_results = sp.search(q=search_query, type='track', limit=10)
                if search_results['tracks']['items']:
                    results = {'tracks': search_results['tracks']['items']}
                    messages.info(request, f"Показуємо популярні треки жанру '{genre}' замість персональних рекомендацій")
                    print("Using search results as fallback")
                else:
                    raise Exception("No search results found")
            except Exception as e3:
                print(f"Search fallback failed: {e3}")
                
    except Exception as e:
        print(f"General error: {e}")
        
    # Final fallback - if everything fails, try basic popular tracks
    if not results:
        try:
            # Try to get some popular tracks as absolute last resort
            search_results = sp.search(q='popular', type='track', limit=10)
            if search_results['tracks']['items']:
                results = {'tracks': search_results['tracks']['items']}
                messages.warning(request, "Не вдалося знайти рекомендації для вашого жанру. Показуємо популярні треки.")
            else:
                messages.error(request, "Не вдалося отримати рекомендації. Спробуйте пізніше або оберіть інший жанр.")
                return redirect('preferences')
        except:
            messages.error(request, "Не вдалося отримати рекомендації. Перевірте підключення до інтернету та спробуйте пізніше.")
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

    return render(request, 'recommender/recommendations.html', {
        'tracks': tracks,
        'spotify_user': spotify_user
    })

@login_required
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