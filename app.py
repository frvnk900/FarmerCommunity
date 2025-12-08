from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
import hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max file size

# Allowed file extensions for media uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('farmer_community.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create posts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT,
            media_type TEXT,  -- 'text', 'image', 'video'
            media_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create likes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id),
            UNIQUE(user_id, post_id)
        )
    ''')
    
    # Create comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('farmer_community.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Get posts with user info and like counts
    posts = conn.execute('''
        SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as like_count,
        (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) as comment_count
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    ''').fetchall()

    # Get comments for each post
    post_comments = {}
    for post in posts:
        comments = conn.execute('''
            SELECT c.*, u.username
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id = ?
            ORDER BY c.created_at ASC
        ''', (post['id'],)).fetchall()
        post_comments[post['id']] = comments

    # Get current user's like status for each post
    liked_posts = []
    if 'user_id' in session:
        liked_posts = [row[0] for row in conn.execute(
            'SELECT post_id FROM likes WHERE user_id = ?', (session['user_id'],)
        ).fetchall()]

    conn.close()

    return render_template('index.html', posts=posts, post_comments=post_comments, liked_posts=liked_posts)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Get the specific post
    post = conn.execute('''
        SELECT p.*, u.username
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    ''', (post_id,)).fetchone()

    if not post:
        conn.close()
        return redirect(url_for('index'))

    # Get comments for the post
    comments = conn.execute('''
        SELECT c.*, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()

    # Get current user's like status for the post
    liked = False
    if 'user_id' in session:
        result = conn.execute(
            'SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?',
            (session['user_id'], post_id)
        ).fetchone()
        liked = result is not None

    conn.close()

    return render_template('post.html', post=post, comments=comments, liked=liked)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        
        if not username:
            flash('Username is required')
            return render_template('register.html')
        
        conn = get_db_connection()
        
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
            conn.commit()
            flash('Registration successful')
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
            conn.close()
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('User not found. Please register first.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/post', methods=['GET', 'POST'])
def create_post_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form.get('content', '')
        media_file = request.files.get('media')

        if not content and not media_file:
            flash('Post must have content or media')
            return render_template('create_post.html')

        media_type = None
        media_path = None

        if media_file and allowed_file(media_file.filename):
            filename = secure_filename(media_file.filename)
            # Create a unique filename using timestamp
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{name}_{timestamp}{ext}"

            media_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            media_file.save(media_path)

            # Determine media type
            if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
                media_type = 'image'
            elif ext.lower() in ['.mp4', '.mov', '.avi']:
                media_type = 'video'

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO posts (user_id, content, media_type, media_path)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], content, media_type, media_path))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('create_post.html')

@app.route('/post_action', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form.get('content', '')
    media_file = request.files.get('media')

    if not content and not media_file:
        flash('Post must have content or media')
        return redirect(url_for('create_post_form'))

    media_type = None
    media_path = None

    if media_file and allowed_file(media_file.filename):
        filename = secure_filename(media_file.filename)
        # Create a unique filename using timestamp
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{name}_{timestamp}{ext}"

        media_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        media_file.save(media_path)

        # Determine media type
        if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
            media_type = 'image'
        elif ext.lower() in ['.mp4', '.mov', '.avi']:
            media_type = 'video'

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO posts (user_id, content, media_type, media_path)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], content, media_type, media_path))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            INSERT INTO likes (user_id, post_id)
            VALUES (?, ?)
        ''', (session['user_id'], post_id))
        conn.commit()
    except sqlite3.IntegrityError:
        # If like already exists, unlike instead
        conn.execute('''
            DELETE FROM likes
            WHERE user_id = ? AND post_id = ?
        ''', (session['user_id'], post_id))
        conn.commit()
    
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form['content']
    
    if not content:
        flash('Comment content is required')
        return redirect(request.referrer or url_for('index'))
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO comments (user_id, post_id, content)
        VALUES (?, ?, ?)
    ''', (session['user_id'], post_id, content))
    conn.commit()
    conn.close()
    
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    init_db()
    app.run(debug=True)