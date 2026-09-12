from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["job_search_db"]
users = db["users"]

# Create unique index on username so duplicates are rejected
users.create_index("username", unique=True)


def create_user(username, password, skills, experience, location, preferred_work):
    """Register a new user — stores hashed password, never plain text."""
    user = {
        "username":       username,
        "password":       generate_password_hash(password),
        "skills":         skills,
        "experience":     experience,
        "location":       location,
        "preferred_work": preferred_work,
        "category_scores":  {},
        "search_history":   [],
        "saved_jobs":       [],
        "rejected_jobs":    [],
        "created_at":       datetime.utcnow()
    }
    try:
        users.insert_one(user)
        return True, "Account created successfully"
    except Exception as e:
        return False, "Username already taken"


def get_user(username):
    """Fetch a user document by username."""
    return users.find_one({"username": username})


def verify_password(username, password):
    """Check submitted password against stored hash."""
    user = get_user(username)
    if not user:
        return False
    return check_password_hash(user["password"], password)


def update_category_score(username, category, delta):
    """
    Increment or decrement a category preference score.
    delta = +1 for save, -1 for reject.
    """
    users.update_one(
        {"username": username},
        {"$inc": {f"category_scores.{category}": delta}}
    )


def add_saved_job(username, job):
    """Add a job to the user's saved jobs list."""
    users.update_one(
        {"username": username},
        {"$addToSet": {"saved_jobs": job}}
    )


def add_rejected_job(username, job_title):
    """Add a job title to the user's rejected list."""
    users.update_one(
        {"username": username},
        {"$addToSet": {"rejected_jobs": job_title}}
    )


def add_search_history(username, query):
    """Append a query to search history (keep last 20)."""
    users.update_one(
        {"username": username},
        {"$push": {"search_history": {
            "$each": [query],
            "$slice": -20
        }}}
    )


def get_top_categories(username, n=3):
    """Return the top n categories by score for the For You feed."""
    user = get_user(username)
    if not user or not user.get("category_scores"):
        return []
    scores = user["category_scores"]
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, score in sorted_cats[:n] if score > 0]