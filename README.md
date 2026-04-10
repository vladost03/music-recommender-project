# 🎵 Music Recommender

A Django web application that generates personalized music recommendations using the Spotify API — based on your favorite genres or your personal listening history.

---

## Prerequisites

- Python 3.10+
- A [Spotify Developer](https://developer.spotify.com/dashboard) account
- `pip` package manager

---

## 1. Clone the Repository

```bash
git clone https://github.com/vladost03/music-recommender-project.git
cd music-recommender-project
```

---

## 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If there is no `requirements.txt`, install manually:

```bash
pip install django spotipy python-dotenv django-widget-tweaks
```

---

## 4. Set Up Spotify API Credentials

1. Go to [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Click **Create App**
3. Set the **Redirect URI** to: `http://127.0.0.1:8000/spotify/callback/`
4. Copy your **Client ID** and **Client Secret**

---

## 5. Configure Environment Variables

Create a `.env` file in the project root (next to `manage.py`):

```env
DJANGO_SECRET_KEY=your-secret-django-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/spotify/callback/
```

To generate a secure Django secret key, run:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 6. Apply Database Migrations

```bash
python manage.py migrate
```

---

## 7. Run the Development Server

```bash
python manage.py runserver
```

Open your browser and navigate to: **http://127.0.0.1:8000**

---

## Usage

1. Click **"Увійти через Spotify"** (Log in with Spotify) on the welcome page
2. Authorize the app in the Spotify popup
3. On the **Preferences** page, choose either:
   - A specific genre (Rock, Pop, Jazz, etc.)
   - **Personal Mix** — recommendations based on your actual listening history
4. View your 10 personalized track recommendations with direct Spotify links
5. Click your username in the navbar to see your top tracks, artists, and genres

---

## Project Structure

```
music_recommender/          # Django project settings & config
recommender/
├── services/
│   ├── recommendation_service.py   # Main orchestration logic
│   ├── search_service.py           # Genre-based search
│   └── personal_recommendations_service.py  # History-based mix
├── templates/recommender/          # HTML templates
├── models.py                       # DB models
├── views.py                        # View functions
├── urls.py                         # URL routing
└── forms.py                        # Preference form
```

---

## Notes

- The app uses **session-based** user identification — no account registration required beyond Spotify login.
- Spotify requires your account to be added as a **test user** in the Developer Dashboard while the app is in development mode.
- To add test users: Dashboard → Your App → Settings → User Management.
