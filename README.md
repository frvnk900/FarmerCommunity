# Farmers Community

Simple Flask application where farmers can sign up, login, view posts, like, comment, search users, and add posts with photo+text or photo only.

## Features
- Signup / Login (username + password)
- Home feed: see all posts, like, comment
- Create new post with photo + optional text (stored in MongoDB GridFS)
- Search users by username
- Production-ready entry (wsgi: app:app), requirements.txt included

## Setup (production-ready)
1. Create virtualenv, install requirements:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create `.env` file (a sample is provided as `.env.sample`). The provided MONGODB_URI will work:
   ```
   MONGODB_URI="database"
   SECRET_KEY="change_this_in_production"
   ```
3. Run with a production WSGI server, for example gunicorn:
   ```
   gunicorn --bind 0.0.0.0:8000 app:app
   ```
   Or use waitress on Windows:
   ```
   waitress-serve --listen=0.0.0.0:8000 app:app
   ```
4. Open http://localhost:8000

## Notes
- Images are stored in MongoDB GridFS.
- This is a minimal starter app; for a production deployment add HTTPS, robust session & cookie handling, rate limiting, input validation, and more.
