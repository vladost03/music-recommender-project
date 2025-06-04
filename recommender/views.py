from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from collections import Counter
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

from .forms import UserPreferenceForm
from .models import TrackRecommendation
from .services.recommendation_service import recommendations as generate_recommendations

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


def get_user_top_stats(request):
    """Get user's top 5 tracks, artists, and genres based on recent listening"""
    if 'access_token' not in request.session:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        access_token = request.session['access_token']
        sp = spotipy.Spotify(auth=access_token)
        
        # Get top tracks (short term - last 4 weeks)
        top_tracks_response = sp.current_user_top_tracks(limit=5, time_range='short_term')
        top_tracks = []
        for track in top_tracks_response['items']:
            artists = ', '.join([artist['name'] for artist in track['artists']])
            top_tracks.append(f"{artists} - {track['name']}")
        
        # Get top artists (short term - last 4 weeks)
        top_artists_response = sp.current_user_top_artists(limit=5, time_range='short_term')
        top_artists = [artist['name'] for artist in top_artists_response['items']]
        
        # Get genres from top artists
        all_genres = []
        for artist in top_artists_response['items']:
            all_genres.extend(artist.get('genres', []))
        
        # Count genres and get top 5
        genre_counts = Counter(all_genres)
        top_genres = [genre for genre, count in genre_counts.most_common(5)]
        
        # If we don't have enough data from short term, try medium term
        if len(top_tracks) < 3:
            try:
                medium_tracks = sp.current_user_top_tracks(limit=10, time_range='medium_term')
                for track in medium_tracks['items']:
                    if len(top_tracks) >= 5:
                        break
                    artists = ', '.join([artist['name'] for artist in track['artists']])
                    track_name = f"{artists} - {track['name']}"
                    if track_name not in top_tracks:
                        top_tracks.append(track_name)
            except:
                pass
        
        if len(top_artists) < 3:
            try:
                medium_artists = sp.current_user_top_artists(limit=10, time_range='medium_term')
                for artist in medium_artists['items']:
                    if len(top_artists) >= 5:
                        break
                    if artist['name'] not in top_artists:
                        top_artists.append(artist['name'])
            except:
                pass
        
        return JsonResponse({
            'top_tracks': top_tracks[:5],
            'top_artists': top_artists[:5],
            'top_genres': top_genres[:5]
        })
        
    except Exception as e:
        print(f"Error getting top stats: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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


def recommendations(request):
    """Wrapper function that calls the service"""
    return generate_recommendations(request, sp_oauth)


def recommendations_view(request):
    recommendations_list = TrackRecommendation.objects.filter(
        user_session_key=request.session.session_key
    ).order_by('-recommended_at')
    spotify_user = get_spotify_user_info(request)
    return render(request, 'recommender/recommendations.html', {
        'recommendations': recommendations_list,
        'spotify_user': spotify_user
    })


def spotify_logout(request):
    """Clear Spotify session data"""
    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    messages.success(request, "Ви вийшли з Spotify.")
    return redirect('welcome')