import random


def get_search_based_recommendations(sp, genre, limit=10):
    """
    Get recommendations using search with enhanced strategies for better variety
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
        # Enhanced search strategies for better variety
        for base_query in queries[:5]: 
            try:
                print(f"Searching for base genre: {base_query}")
                
                # Use different search strategies for variety (same as in personal mix)
                search_strategies = [
                    f'{base_query} NOT mainstream',  # Less popular tracks
                    f'{base_query} indie',  # Independent artists
                    f'{base_query} underground',  # Underground tracks
                    f'genre:"{base_query}"',  # Standard genre search
                    f'{base_query} popular',  # Popular in genre
                    f'{base_query} new',  # New releases
                    f'{base_query} alternative',  # Alternative versions
                ]
                
                # Use multiple strategies for this genre
                strategies_to_use = random.sample(search_strategies, min(3, len(search_strategies)))
                
                for strategy in strategies_to_use:
                    try:
                        print(f"Searching with strategy: {strategy}")
                        
                        results = sp.search(q=strategy, type='track', limit=3)
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
                        print(f"Search failed for strategy '{strategy}': {e}")
                        continue
                
                # Also do a basic search without strategy for backup
                try:
                    results = sp.search(q=base_query, type='track', limit=2)
                    if results['tracks']['items']:
                        for track in results['tracks']['items']:
                            artist_names = [artist['name'] for artist in track['artists']]
                            existing_artists = [t['artists'][0]['name'] for t in all_tracks]
                            artist_count = sum(1 for existing in existing_artists if existing in artist_names)
                            if artist_count < 2:
                                all_tracks.append(track)
                except Exception as e:
                    print(f"Basic search failed for '{base_query}': {e}")
                    
            except Exception as e:
                print(f"Search failed for query '{base_query}': {e}")
                continue
        
        # Remove duplicates based on track ID and track+artist combination
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
        
        # If we still don't have enough tracks, do additional searches
        if len(unique_tracks) < limit:
            try:
                # Try broader searches
                broader_searches = [
                    f'{genre} music',
                    f'{genre} songs',
                    f'best {genre}',
                    f'{genre} hits'
                ]
                
                for search_term in broader_searches:
                    if len(unique_tracks) >= limit:
                        break
                        
                    try:
                        results = sp.search(q=search_term, type='track', limit=5)
                        if results['tracks']['items']:
                            for track in results['tracks']['items']:
                                if len(unique_tracks) >= limit:
                                    break
                                    
                                track_id = track['id']
                                track_combo = (track['name'].lower(), track['artists'][0]['name'].lower())
                                
                                if track_id not in seen_ids and track_combo not in seen_combinations:
                                    seen_ids.add(track_id)
                                    seen_combinations.add(track_combo)
                                    unique_tracks.append(track)
                    except Exception as e:
                        print(f"Broader search failed for '{search_term}': {e}")
                        continue
            except Exception as e:
                print(f"Additional searches failed: {e}")
        
        # Shuffle and limit results
        random.shuffle(unique_tracks)
        print(f"Generated {len(unique_tracks)} unique tracks for genre '{genre}'")
        return unique_tracks[:limit]
        
    except Exception as e:
        print(f"All search attempts failed: {e}")
        # Final fallback - search for popular music
        try:
            results = sp.search(q='popular music', type='track', limit=limit)
            return results['tracks']['items'] if results['tracks']['items'] else []
        except:
            return []