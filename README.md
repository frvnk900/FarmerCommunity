# Farmer Community App

A simple Flask-based social media application for farmers to share experiences, tips, and connect with each other.

## Features

- User registration with username only
- Create posts with text, photos, or videos (under 20MB)
- Like and comment on posts
- View community feed
- Separate post detail pages
- Elegant UI with floating action button for posting

## Local Development

### Requirements

- Python 3.7+
- Flask
- SQLite (comes with Python)

### Setup Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Open your browser and go to `http://localhost:5000`

### Usage

1. Register with a username
2. Login to your account
3. Create posts with text or media using the floating circular button
4. Like and comment on other farmers' posts
5. View individual post details with all comments

## Production Deployment on Vercel

### Prerequisites

- A Vercel account
- Git repository with this code

### Deployment Steps

1. Push your code to a Git repository
2. Import the project into Vercel
3. Vercel will automatically detect this as a Python project
4. Make sure to set the build command to install dependencies
5. In your project settings, set the following environment variable:
   - `SECRET_KEY`: A random secret key for session management

### Important Note about Production Deployment

This application uses SQLite for simplicity, but **SQLite is not suitable for production serverless environments** like Vercel. SQLite databases require persistent file storage, which serverless functions don't provide. For a real production deployment, you would need to:

1. Replace SQLite with a database service like PostgreSQL or MySQL
2. Update the database connection logic in `app.py`
3. Use a database connection pooling library like SQLAlchemy with a cloud database

For demonstration purposes, this application will work in development but won't maintain data in a serverless production environment.

### Production Configuration

If deploying to Vercel:
1. The project structure is already configured with `vercel.json`
2. Make sure the `/static/uploads` directory has appropriate permissions
3. For file uploads to work properly in production, you may need to store files in a cloud storage service instead of local filesystem

### Environment Variables

- `SECRET_KEY`: Set this to a secure random string for production
- `UPLOAD_FOLDER`: (Optional) Set to specify where uploaded files are stored (defaults to `static/uploads`)

## Folder Structure

```
FarmerCommunity/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel configuration
├── wsgi.py            # WSGI entry point
├── templates/         # HTML templates
│   ├── index.html     # Main feed page
│   ├── post.html      # Single post view
│   ├── create_post.html # Post creation page
│   ├── login.html     # Login page
│   └── register.html  # Registration page
├── static/            # Static assets
│   └── uploads/       # User uploaded files
└── README.md          # This file
```

## Technologies Used

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Styling**: CSS with Font Awesome icons
- **Deployment**: Vercel