import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import gridfs
from bson.objectid import ObjectId
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------
# MONGODB ATLAS CONNECTION (NO LOCALHOST EVER)
# ---------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise Exception("MONGODB_URI is missing in .env")

client = MongoClient(MONGODB_URI)

# DATABASE CREATED DYNAMICALLY
db = client["farmers_community"]

# Collections
users = db.users
posts = db.posts
fs = gridfs.GridFS(db)

# ---------------------------------------------
# FLASK APP SETUP
# ---------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "prod_secret_key")
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# ---------------------------------------------
# HELPERS
# ---------------------------------------------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return users.find_one({"_id": ObjectId(uid)})

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("home"))
    return redirect(url_for("login"))

# ---------------------------------------------
# SIGNUP
# ---------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("signup.html", error="Provide username and password.")

        if users.find_one({"username": username}):
            return render_template("signup.html", error="Username already exists.")

        pw_hash = generate_password_hash(password)
        uid = users.insert_one({
            "username": username,
            "password": pw_hash,
            "created_at": datetime.utcnow()
        }).inserted_id

        session["user_id"] = str(uid)
        return redirect(url_for("home"))

    return render_template("signup.html")

# ---------------------------------------------
# LOGIN
# ---------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = users.find_one({"username": username})
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid credentials.")

        session["user_id"] = str(user["_id"])
        return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------------------------------------
# HOME FEED
# ---------------------------------------------
@app.route("/home")
def home():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    all_posts = list(posts.find().sort("created_at", -1))

    # Build a user map to avoid querying users repeatedly in the template
    user_map = {}
    for u in users.find():
        user_map[str(u["_id"])] = u["username"]

    # Convert ObjectIds to strings for template use
    for p in all_posts:
        p["_id"] = str(p["_id"])
        p["user_id"] = str(p["user_id"])
        p["username"] = user_map.get(p["user_id"], "User")

        # Convert comment user_ids to strings
        for c in p.get("comments", []):
            c["user_id"] = str(c["user_id"])

    return render_template("home.html", posts=all_posts, user=user, user_map=user_map)

# ---------------------------------------------
# NEW POST
# ---------------------------------------------
@app.route("/post/new", methods=["GET", "POST"])
def new_post():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        file = request.files.get("photo")

        photo_id = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            content = file.read()
            photo_id = fs.put(content, filename=filename, content_type=file.content_type)

        if not text and not photo_id:
            return render_template("post_new.html", error="Add photo or text.")

        posts.insert_one({
            "user_id": user["_id"],
            "text": text,
            "photo_id": photo_id,
            "likes": [],
            "comments": [],
            "created_at": datetime.utcnow()
        })

        return redirect(url_for("home"))

    return render_template("post_new.html")

# ---------------------------------------------
# IMAGE STREAM
# ---------------------------------------------
@app.route("/image/<id>")
def image(id):
    try:
        file = fs.get(ObjectId(id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type)
    except:
        return "", 404

# ---------------------------------------------
# LIKE POST
# ---------------------------------------------
@app.route("/post/<id>/like", methods=["POST"])
def like_post(id):
    user = current_user()
    if not user:
        return jsonify({"error": "auth"}), 401

    post = posts.find_one({"_id": ObjectId(id)})
    if not post:
        return jsonify({"error": "not found"}), 404

    uid = user["_id"]

    if uid in post.get("likes", []):
        posts.update_one({"_id": post["_id"]}, {"$pull": {"likes": uid}})
        status = "unliked"
    else:
        posts.update_one({"_id": post["_id"]}, {"$addToSet": {"likes": uid}})
        status = "liked"

    new_likes = posts.find_one({"_id": post["_id"]})["likes"]
    return jsonify({"status": status, "likes": new_likes})

# ---------------------------------------------
# COMMENT POST
# ---------------------------------------------
@app.route("/post/<id>/comment", methods=["POST"])
def comment_post(id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    text = request.form.get("comment", "").strip()
    if not text:
        return redirect(url_for("home"))

    posts.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"comments": {
            "user_id": user["_id"],
            "text": text,
            "created_at": datetime.utcnow()
        }}}
    )

    return redirect(url_for("home"))

# ---------------------------------------------
# SEARCH USERS
# ---------------------------------------------
@app.route("/search")
def search():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()
    results = []

    if q:
        results = list(users.find({"username": {"$regex": q, "$options": "i"}}))

    return render_template("search.html", results=results, q=q)

# ---------------------------------------------
# USER PROFILE
# ---------------------------------------------
@app.route("/user/<username>")
def profile(username):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    target = users.find_one({"username": username})
    if not target:
        return "User not found", 404

    user_posts = list(posts.find({"user_id": target["_id"]}).sort("created_at", -1))

    return render_template("profile.html", profile_user=target, posts=user_posts)

# ---------------------------------------------
# PROD SERVER
# ---------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
