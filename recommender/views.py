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

def get_personal_mix_recommendations(sp, limit=10):
    """
    Get recommendations based on user's top genres from listening history
    """
    try:
        # Get user's top genres
        top_genres = get_user_top_genres(sp)
        
        if not top_genres:
            print("No top genres found, falling back to user's top tracks")
            return get_recommendations_from_top_tracks(sp, limit)
        
        print(f"Generating personal mix from genres: {top_genres}")
        
        all_tracks = []
        tracks_per_genre = max(2, limit // len(top_genres))  # Distribute tracks across genres
        
        for genre in top_genres:
            try:
                # Search for tracks in this genre
                search_queries = [
                    f'genre:"{genre}"',
                    f'{genre}',
                    f'{genre} popular'
                ]
                
                genre_tracks = []
                for query in search_queries:
                    try:
                        results = sp.search(q=query, type='track', limit=tracks_per_genre)
                        if results['tracks']['items']:
                            genre_tracks.extend(results['tracks']['items'])
                            break  # Use first successful query
                    except Exception as e:
                        print(f"Search failed for query '{query}': {e}")
                        continue
                
                # Add tracks from this genre
                if genre_tracks:
                    # Remove duplicates and add to main list
                    seen_ids = set(track['id'] for track in all_tracks)
                    for track in genre_tracks:
                        if track['id'] not in seen_ids:
                            all_tracks.append(track)
                            seen_ids.add(track['id'])
                            if len(all_tracks) >= limit:
                                break
                
                if len(all_tracks) >= limit:
                    break
                    
            except Exception as e:
                print(f"Error getting tracks for genre '{genre}': {e}")
                continue
        
        # If we don't have enough tracks, try to get user's top tracks
        if len(all_tracks) < limit // 2:
            print("Not enough tracks from genres, adding top tracks")
            top_tracks = get_recommendations_from_top_tracks(sp, limit - len(all_tracks))
            
            # Add non-duplicate top tracks
            seen_ids = set(track['id'] for track in all_tracks)
            for track in top_tracks:
                if track['id'] not in seen_ids and len(all_tracks) < limit:
                    all_tracks.append(track)
        
        # Shuffle for variety
        random.shuffle(all_tracks)
        return all_tracks[:limit]
        
    except Exception as e:
        print(f"Error in personal mix recommendations: {e}")
        return get_recommendations_from_top_tracks(sp, limit)

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