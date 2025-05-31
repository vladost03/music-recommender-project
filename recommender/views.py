from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import random

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
            
        print(f"Token obtained successfully")
        return redirect('preferences')
    except Exception as e:
        print(f"Token error: {e}")
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

def get_search_based_recommendations(sp, genre, limit=10):
    """
    Get recommendations using search instead of the deprecated recommendations endpoint
    """
    # Define search queries for different genres
    genre_queries = {
        'rock': ['rock', 'indie rock', 'alternative rock', 'classic rock', 'hard rock'],
        'pop': ['pop', 'indie pop', 'dance pop', 'electropop', 'synth pop'],
        'jazz': ['jazz', 'smooth jazz', 'bebop', 'contemporary jazz', 'fusion'],
        'hip-hop': ['hip hop', 'rap', 'trap', 'conscious hip hop', 'old school hip hop'],
        'classical': ['classical', 'orchestra', 'piano classical', 'baroque', 'romantic classical'],
        'electronic': ['electronic', 'house', 'techno', 'ambient', 'downtempo', 'edm'],
        'reggae': ['reggae', 'dub', 'ska', 'roots reggae', 'dancehall'],
        'metal': ['metal', 'heavy metal', 'death metal', 'black metal', 'progressive metal'],
        'blues': ['blues', 'delta blues', 'electric blues', 'blues rock', 'chicago blues'],
        'country': ['country', 'country rock', 'folk country', 'bluegrass', 'americana']
    }
    
    queries = genre_queries.get(genre.lower(), [genre])
    all_tracks = []
    
    try:
        # Search for tracks using multiple queries for variety
        for query in queries[:5]:  # Use first 3 queries to avoid rate limits
            try:
                print(f"Searching for: {query}")
                
                # Search for popular tracks in the genre
                results = sp.search(q=f'genre:"{query}"', type='track', limit=5)
                if results['tracks']['items']:
                    all_tracks.extend(results['tracks']['items'])
                
                # Also search without genre prefix for more results
                results = sp.search(q=query, type='track', limit=3)
                if results['tracks']['items']:
                    all_tracks.extend(results['tracks']['items'])
                    
            except Exception as e:
                print(f"Search failed for query '{query}': {e}")
                continue
        
        # Remove duplicates based on track ID
        seen_ids = set()
        unique_tracks = []
        for track in all_tracks:
            if track['id'] not in seen_ids:
                seen_ids.add(track['id'])
                unique_tracks.append(track)
        
        # Shuffle and limit results
        random.shuffle(unique_tracks)
        return unique_tracks[:limit]
        
    except Exception as e:
        print(f"All search attempts failed: {e}")
        # Final fallback - search for popular music
        try:
            results = sp.search(q='popular music', type='track', limit=limit)
            return results['tracks']['items'] if results['tracks']['items'] else []
        except:
            return []

def get_user_top_genres(sp, limit=50):
    """
    Analyze user's recently played tracks to determine top genres
    """
    try:
        # Get recently played tracks
        recent_tracks = sp.current_user_recently_played(limit=limit)
        
        if not recent_tracks or not recent_tracks.get('items'):
            print("No recent tracks found")
            return []
        
        # Get unique artist IDs from recent tracks
        artist_ids = []
        track_artists = set()
        
        for item in recent_tracks['items']:
            track = item['track']
            for artist in track['artists']:
                if artist['id'] not in track_artists:
                    track_artists.add(artist['id'])
                    artist_ids.append(artist['id'])
        
        # Limit to avoid API rate limits
        artist_ids = artist_ids[:20]
        
        if not artist_ids:
            return []
        
        # Get artist details in batches (Spotify API allows max 50 artists per request)
        all_genres = []
        batch_size = 20  # Conservative batch size
        
        for i in range(0, len(artist_ids), batch_size):
            batch = artist_ids[i:i + batch_size]
            try:
                artists_info = sp.artists(batch)
                
                for artist in artists_info['artists']:
                    if artist and artist.get('genres'):
                        all_genres.extend(artist['genres'])
                        
            except Exception as e:
                print(f"Error getting artist info for batch: {e}")
                continue
        
        if not all_genres:
            print("No genres found from artists")
            return []
        
        # Count genre occurrences
        genre_counts = {}
        for genre in all_genres:
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
        
        # Sort by popularity and return top 5
        top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        print(f"User's top genres: {[genre for genre, count in top_genres]}")
        return [genre for genre, count in top_genres]
        
    except Exception as e:
        print(f"Error analyzing user genres: {e}")
        return []

def get_recommendations_from_top_tracks(sp, limit=10):
    """
    Fallback: Get recommendations based on user's top tracks
    """
    try:
        # Get user's top tracks (short term = last 4 weeks)
        top_tracks = sp.current_user_top_tracks(limit=20, time_range='short_term')
        
        if not top_tracks or not top_tracks.get('items'):
            # Try medium term (last 6 months)
            top_tracks = sp.current_user_top_tracks(limit=20, time_range='medium_term')
        
        if not top_tracks or not top_tracks.get('items'):
            print("No top tracks found")
            return []
        
        # Get artists from top tracks
        top_artists = set()
        for track in top_tracks['items']:
            for artist in track['artists']:
                top_artists.add(artist['name'])
        
        # Search for tracks by these artists
        all_tracks = []
        for artist_name in list(top_artists)[:5]:  # Limit to prevent too many API calls
            try:
                results = sp.search(q=f'artist:"{artist_name}"', type='track', limit=3)
                if results['tracks']['items']:
                    all_tracks.extend(results['tracks']['items'])
                    
            except Exception as e:
                print(f"Error searching for artist '{artist_name}': {e}")
                continue
        
        # Remove duplicates
        seen_ids = set()
        unique_tracks = []
        for track in all_tracks:
            if track['id'] not in seen_ids:
                seen_ids.add(track['id'])
                unique_tracks.append(track)
        
        random.shuffle(unique_tracks)
        return unique_tracks[:limit]
        
    except Exception as e:
        print(f"Error getting recommendations from top tracks: {e}")
        return []

def get_personal_mix_recommendations(sp, limit=10):
    """
    Get recommendations based on user's top genres from listening history with better variety
    """
    try:
        # Get user's top genres
        top_genres = get_user_top_genres(sp)
        
        if not top_genres:
            print("No top genres found, falling back to user's top tracks")
            return get_recommendations_from_top_tracks(sp, limit)
        
        print(f"Generating personal mix from genres: {top_genres}")
        
        all_tracks = []
        
        # Strategy 1: Get tracks from user's top genres with varied search queries
        for i, genre in enumerate(top_genres):
            try:
                # Use different search strategies for variety
                search_strategies = [
                    f'{genre} NOT mainstream',  # Less popular tracks
                    f'{genre} indie',  # Independent artists
                    f'{genre} underground',  # Underground tracks
                    f'genre:"{genre}"',  # Standard genre search
                    f'{genre} popular',  # Popular in genre
                ]
                
                # Randomly select a strategy for this genre
                strategy = random.choice(search_strategies)
                
                print(f"Searching with strategy: {strategy}")
                
                results = sp.search(q=strategy, type='track', limit=4)
                if results['tracks']['items']:
                    # Add tracks with variety check
                    for track in results['tracks']['items']:
                        # Check if we already have a track by this artist
                        artist_names = [artist['name'] for artist in track['artists']]
                        existing_artists = [t['artists'][0]['name'] for t in all_tracks]
                        
                        # Add track if we don't have too many from same artist
                        artist_count = sum(1 for existing in existing_artists if existing in artist_names)
                        if artist_count < 2:  # Max 2 tracks per artist
                            all_tracks.append(track)
                            
            except Exception as e:
                print(f"Error getting tracks for genre '{genre}': {e}")
                continue
        
        # Strategy 2: Add tracks from user's top artists (different from their top tracks)
        try:
            top_artists = sp.current_user_top_artists(limit=10, time_range='short_term')
            if top_artists and top_artists.get('items'):
                for artist in top_artists['items'][:5]:  # Top 5 artists
                    try:
                        # Get artist's albums and pick random tracks
                        albums = sp.artist_albums(artist['id'], album_type='album,single', limit=5)
                        if albums and albums.get('items'):
                            random_album = random.choice(albums['items'])
                            album_tracks = sp.album_tracks(random_album['id'], limit=5)
                            if album_tracks and album_tracks.get('items'):
                                random_track_data = random.choice(album_tracks['items'])
                                # Get full track info
                                full_track = sp.track(random_track_data['id'])
                                if full_track:
                                    # Check if not already in list
                                    if not any(t['id'] == full_track['id'] for t in all_tracks):
                                        all_tracks.append(full_track)
                    except Exception as e:
                        print(f"Error getting tracks for artist {artist['name']}: {e}")
                        continue
        except Exception as e:
            print(f"Error getting top artists: {e}")
        
        # Strategy 3: Add some completely random tracks from user's recently played artists
        try:
            recent_tracks = sp.current_user_recently_played(limit=30)
            if recent_tracks and recent_tracks.get('items'):
                # Get unique artists from recent tracks
                recent_artists = set()
                for item in recent_tracks['items']:
                    for artist in item['track']['artists']:
                        recent_artists.add((artist['id'], artist['name']))
                
                # Pick random artists and get their random tracks
                random_artists = random.sample(list(recent_artists), min(5, len(recent_artists)))
                for artist_id, artist_name in random_artists:
                    try:
                        # Search for tracks by this artist that user might not know
                        results = sp.search(q=f'artist:"{artist_name}" NOT popular', type='track', limit=3)
                        if results['tracks']['items']:
                            random_track = random.choice(results['tracks']['items'])
                            if not any(t['id'] == random_track['id'] for t in all_tracks):
                                all_tracks.append(random_track)
                    except Exception as e:
                        print(f"Error getting random tracks for {artist_name}: {e}")
                        continue
        except Exception as e:
            print(f"Error getting recent tracks for variety: {e}")
        
        # Remove duplicates more carefully
        seen_ids = set()
        seen_combinations = set()  # Track + Artist combination
        unique_tracks = []
        
        for track in all_tracks:
            track_id = track['id']
            track_combo = (track['name'].lower(), track['artists'][0]['name'].lower())
            
            if track_id not in seen_ids and track_combo not in seen_combinations:
                seen_ids.add(track_id)
                seen_combinations.add(track_combo)
                unique_tracks.append(track)
        
        # If we still don't have enough variety, add some from different time periods
        if len(unique_tracks) < limit:
            try:
                # Try getting tracks from different time ranges
                for time_range in ['medium_term', 'long_term']:
                    if len(unique_tracks) >= limit:
                        break
                        
                    top_tracks_period = sp.current_user_top_tracks(limit=10, time_range=time_range)
                    if top_tracks_period and top_tracks_period.get('items'):
                        for track in top_tracks_period['items']:
                            if len(unique_tracks) >= limit:
                                break
                            if track['id'] not in seen_ids:
                                seen_ids.add(track['id'])
                                unique_tracks.append(track)
            except Exception as e:
                print(f"Error getting tracks from different time periods: {e}")
        
        # Final shuffle for randomness
        random.shuffle(unique_tracks)
        
        print(f"Generated {len(unique_tracks)} unique tracks for personal mix")
        return unique_tracks[:limit]
        
    except Exception as e:
        print(f"Error in personal mix recommendations: {e}")
        return get_recommendations_from_top_tracks(sp, limit)
    
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
    
    # Check if user selected personal mix
    if genre == 'personal_mix':
        print("Getting personal mix recommendations based on user's listening history")
        tracks_data = get_personal_mix_recommendations(sp, limit=10)
        recommendation_type = "персонального міксу на основі вашої історії прослуховування"
    else:
        # Get recommendations using search-based approach for specific genre
        print(f"Getting search-based recommendations for genre: {genre}")
        tracks_data = get_search_based_recommendations(sp, genre, limit=10)
        recommendation_type = f"жанру '{genre}'"
    
    if not tracks_data:
        if genre == 'personal_mix':
            messages.error(request, "Не вдалося створити персональний мікс. Можливо, у вас недостатньо історії прослуховування. Спробуйте обрати конкретний жанр.")
        else:
            messages.error(request, "Не вдалося знайти треки для вашого жанру. Спробуйте інший жанр.")
        return redirect('preferences')

    # Clear previous recommendations and save new ones
    TrackRecommendation.objects.filter(user_session_key=request.session.session_key).delete()
    
    # Save new recommendations to database
    for track in tracks_data:
        TrackRecommendation.objects.create(
            user_session_key=request.session.session_key,
            track_name=track['name'],
            artist_name=track['artists'][0]['name'],
            spotify_url=track['external_urls']['spotify']
        )

    messages.success(request, f"Знайдено {len(tracks_data)} рекомендацій для {recommendation_type}!")

    # Get the saved recommendations to display
    recommendations = TrackRecommendation.objects.filter(
        user_session_key=request.session.session_key
    ).order_by('-recommended_at')

    return render(request, 'recommender/recommendations.html', {
        'recommendations': recommendations,
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