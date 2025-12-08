from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import threading
from time import sleep

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key_for_development')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max file size

# Data file path
DATA_FILE = 'data.json'

# Allowed file extensions for media uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

# Thread lock for file operations
file_lock = threading.Lock()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_data():
    """Read data from JSON file"""
    with file_lock:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, return empty data
                    return {"users": {}, "posts": {}, "likes": {}, "comments": {}, "next_ids": {"user_id": 1, "post_id": 1, "comment_id": 1, "like_id": 1}}
        else:
            # Initialize with empty data
            return {"users": {}, "posts": {}, "likes": {}, "comments": {}, "next_ids": {"user_id": 1, "post_id": 1, "comment_id": 1, "like_id": 1}}

def write_data(data):
    """Write data to JSON file with error handling"""
    with file_lock:
        try:
            # Create backup
            if os.path.exists(DATA_FILE):
                os.rename(DATA_FILE, DATA_FILE + '.bak')
            
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Remove backup if successful
            if os.path.exists(DATA_FILE + '.bak'):
                os.remove(DATA_FILE + '.bak')
                
        except Exception as e:
            # Restore from backup if write failed
            if os.path.exists(DATA_FILE + '.bak'):
                os.rename(DATA_FILE + '.bak', DATA_FILE)
            print(f"Error writing to data file: {e}")
            raise e

def get_next_id(entity_type):
    """Get and increment the next ID for the given entity type"""
    data = read_data()
    next_id = data["next_ids"][entity_type]
    data["next_ids"][entity_type] = next_id + 1
    write_data(data)
    return next_id

def init_db():
    """Initialize the JSON data file if it doesn't exist"""
    if not os.path.exists(DATA_FILE):
        data = {
            "users": {},
            "posts": {},
            "likes": {},
            "comments": {},
            "next_ids": {"user_id": 1, "post_id": 1, "comment_id": 1, "like_id": 1}
        }
        write_data(data)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    data = read_data()
    
    # Get posts with user info and like counts
    posts = []
    for post_id, post in data['posts'].items():
        post_user = data['users'].get(str(post['user_id']), {})
        post['username'] = post_user.get('username', 'Unknown')
        
        # Count likes for this post
        like_count = sum(1 for like in data['likes'].values() if like['post_id'] == int(post_id))
        post['like_count'] = like_count
        
        # Count comments for this post
        comment_count = sum(1 for comment in data['comments'].values() if comment['post_id'] == int(post_id))
        post['comment_count'] = comment_count
        
        posts.append(post)
    
    # Sort posts by creation time (newest first)
    posts.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Get comments for each post
    post_comments = {}
    for post in posts:
        post_id = post['id']
        post_comments[post_id] = []
        for comment_id, comment in data['comments'].items():
            if comment['post_id'] == post_id:
                comment_user = data['users'].get(str(comment['user_id']), {})
                comment['username'] = comment_user.get('username', 'Unknown')
                post_comments[post_id].append(comment)
        # Sort comments by creation time
        post_comments[post_id].sort(key=lambda x: x['created_at'])
    
    # Get current user's like status for each post
    liked_posts = []
    if 'user_id' in session:
        user_id = session['user_id']
        for like_id, like in data['likes'].items():
            if like['user_id'] == user_id:
                liked_posts.append(like['post_id'])
    
    return render_template('index.html', posts=posts, post_comments=post_comments, liked_posts=liked_posts)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = read_data()

    # Get the specific post
    post = None
    for p_id, p in data['posts'].items():
        if p['id'] == post_id:
            post = p
            break

    if not post:
        return redirect(url_for('index'))

    # Get the post owner's username
    post_user = data['users'].get(str(post['user_id']), {})
    post['username'] = post_user.get('username', 'Unknown')

    # Count likes for this post
    like_count = sum(1 for like in data['likes'].values() if like['post_id'] == post_id)
    post['like_count'] = like_count

    # Count comments for this post
    comment_count = sum(1 for comment in data['comments'].values() if comment['post_id'] == post_id)
    post['comment_count'] = comment_count

    # Get comments for the post
    comments = []
    for comment_id, comment in data['comments'].items():
        if comment['post_id'] == post_id:
            comment_user = data['users'].get(str(comment['user_id']), {})
            comment['username'] = comment_user.get('username', 'Unknown')
            comments.append(comment)

    # Sort comments by creation time
    comments.sort(key=lambda x: x['created_at'])

    # Get current user's like status for the post
    liked = False
    if 'user_id' in session:
        user_id = session['user_id']
        for like_id, like in data['likes'].items():
            if like['user_id'] == user_id and like['post_id'] == post_id:
                liked = True
                break

    return render_template('post.html', post=post, comments=comments, liked=liked)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        
        if not username:
            flash('Username is required')
            return render_template('register.html')
        
        data = read_data()
        
        # Check if username already exists
        for user_id, user in data['users'].items():
            if user['username'] == username:
                flash('Username already exists')
                return render_template('register.html')
        
        # Create new user
        user_id = get_next_id('user_id')
        new_user = {
            'id': user_id,
            'username': username,
            'created_at': datetime.now().isoformat()
        }
        
        data['users'][str(user_id)] = new_user
        write_data(data)
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        
        data = read_data()
        
        # Find user by username
        user = None
        for user_id, u in data['users'].items():
            if u['username'] == username:
                user = u
                break
        
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
        
        data = read_data()
        post_id = get_next_id('post_id')
        
        new_post = {
            'id': post_id,
            'user_id': session['user_id'],
            'content': content,
            'media_type': media_type,
            'media_path': media_path,
            'created_at': datetime.now().isoformat()
        }
        
        data['posts'][str(post_id)] = new_post
        write_data(data)
        
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
    
    data = read_data()
    post_id = get_next_id('post_id')
    
    new_post = {
        'id': post_id,
        'user_id': session['user_id'],
        'content': content,
        'media_type': media_type,
        'media_path': media_path,
        'created_at': datetime.now().isoformat()
    }
    
    data['posts'][str(post_id)] = new_post
    write_data(data)
    
    return redirect(url_for('index'))

@app.route('/api/like/<int:post_id>', methods=['POST'])
def api_like_post(post_id):
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401

    data = read_data()

    # Check if like already exists
    like_exists = False
    like_to_remove = None
    for like_id, like in data['likes'].items():
        if like['user_id'] == session['user_id'] and like['post_id'] == post_id:
            like_exists = True
            like_to_remove = like_id
            break

    if like_exists:
        # Remove the like
        del data['likes'][like_to_remove]
        action = 'unliked'
    else:
        # Add the like
        like_id = get_next_id('like_id')
        new_like = {
            'id': like_id,
            'user_id': session['user_id'],
            'post_id': post_id,
            'created_at': datetime.now().isoformat()
        }
        data['likes'][str(like_id)] = new_like
        action = 'liked'

    write_data(data)

    # Recalculate like count for this post
    like_count = sum(1 for like in data['likes'].values() if like['post_id'] == post_id)

    return {
        'status': 'success',
        'action': action,
        'like_count': like_count,
        'liked': action == 'liked'
    }

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = read_data()

    # Check if like already exists
    like_exists = False
    like_to_remove = None
    for like_id, like in data['likes'].items():
        if like['user_id'] == session['user_id'] and like['post_id'] == post_id:
            like_exists = True
            like_to_remove = like_id
            break

    if like_exists:
        # Remove the like
        del data['likes'][like_to_remove]
    else:
        # Add the like
        like_id = get_next_id('like_id')
        new_like = {
            'id': like_id,
            'user_id': session['user_id'],
            'post_id': post_id,
            'created_at': datetime.now().isoformat()
        }
        data['likes'][str(like_id)] = new_like

    write_data(data)
    return redirect(request.referrer or url_for('index'))

@app.route('/like_post/<int:post_id>')
def like_post_from_post_page(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = read_data()

    # Check if like already exists
    like_exists = False
    like_to_remove = None
    for like_id, like in data['likes'].items():
        if like['user_id'] == session['user_id'] and like['post_id'] == post_id:
            like_exists = True
            like_to_remove = like_id
            break

    if like_exists:
        # Remove the like
        del data['likes'][like_to_remove]
    else:
        # Add the like
        like_id = get_next_id('like_id')
        new_like = {
            'id': like_id,
            'user_id': session['user_id'],
            'post_id': post_id,
            'created_at': datetime.now().isoformat()
        }
        data['likes'][str(like_id)] = new_like

    write_data(data)
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form['content']

    if not content:
        flash('Comment content is required')
        # Use a specific redirect instead of referrer to avoid issues
        return redirect(url_for('view_post', post_id=post_id))

    data = read_data()
    comment_id = get_next_id('comment_id')

    new_comment = {
        'id': comment_id,
        'user_id': session['user_id'],
        'post_id': post_id,
        'content': content,
        'created_at': datetime.now().isoformat()
    }

    data['comments'][str(comment_id)] = new_comment
    write_data(data)

    return redirect(url_for('view_post', post_id=post_id))

# Production configuration for Vercel
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    init_db()
    app.run(debug=True)
elif os.environ.get('VERCEL'):
    # In Vercel, we initialize the database when the app starts
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    init_db()