from django.shortcuts import render, redirect
from django.contrib import messages
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