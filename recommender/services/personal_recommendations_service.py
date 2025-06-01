import random


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