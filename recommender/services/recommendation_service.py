from django.shortcuts import render, redirect
from django.contrib import messages
import spotipy

from ..models import TrackRecommendation, UserPreference
from .search_service import get_search_based_recommendations
from .personal_recommendations_service import get_personal_mix_recommendations


def refresh_spotify_token(request, sp_oauth):
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


def recommendations(request, sp_oauth):
    """Generate music recommendations based on user preferences"""
    if 'access_token' not in request.session:
        messages.warning(request, "Будь ласка, авторизуйтесь через Spotify.")
        return redirect('spotify-login')

    # Refresh token if needed
    access_token = refresh_spotify_token(request, sp_oauth)
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
    recommendations_list = TrackRecommendation.objects.filter(
        user_session_key=request.session.session_key
    ).order_by('-recommended_at')

    return render(request, 'recommender/recommendations.html', {
        'recommendations': recommendations_list,
        'spotify_user': spotify_user
    })