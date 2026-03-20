
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure random value

# Simple authentication check for now - Clerk will handle the heavy lifting on frontend
def auth_required(f):
    """Simple decorator - in production, you'd verify Clerk JWT tokens here"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For now, we'll rely on frontend Clerk authentication
        # In production, verify the JWT token sent from Clerk frontend
        return f(*args, **kwargs)
    return decorated_function

# Route for reviews page (after all app setup)
@app.route('/review', methods=['GET', 'POST'])
def review():
    if request.method == 'POST':
        name = request.form.get('name')
        role = request.form.get('role')
        title = request.form.get('title')
        text = request.form.get('text')
        stars = int(request.form.get('stars', 5))
        avatar_url = request.form.get('avatar_url')
        from datetime import datetime
        review_doc = {
            'name': name,
            'role': role,
            'title': title,
            'text': text,
            'stars': stars,
            'avatar_url': avatar_url,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        reviews.insert_one(review_doc)
        return redirect(url_for('reviews'))
    return render_template('review.html')
@app.route('/reviews')
def reviews():
    # Fetch up to 4 recent reviews from the database (same logic as before)
    top_reviews = list(reviews.find().sort([('_id', -1)]).limit(4))
    for review in top_reviews:
        name = review.get('name', 'User')
        review['avatar_url'] = review.get('avatar_url') or f"https://api.dicebear.com/7.x/identicon/svg?seed={name}"
        review['role'] = review.get('role', 'User')
        review['title'] = review.get('title', 'Great experience!')
        review['text'] = review.get('text', '')
        review['stars'] = int(review.get('stars', 5))
        review['date'] = str(review.get('date', ''))
    return render_template('reviews.html', top_reviews=top_reviews)

# Jinja2 filter for formatting follower counts
def format_followers(value):
    try:
        value = float(value)
        if value >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value/1_000:.1f}K"
        else:
            return str(int(value))
    except Exception:
        return str(value)
app.jinja_env.filters['format_followers'] = format_followers
client = MongoClient('mongodb://localhost:27017/')
db = client['socioapp']
users = db['users']
reviews = db['reviews']

# Individual stats pages
@app.route('/youtube_stats')
def youtube_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    import logging
    youtube_stats = None
    youtube_logo_url = None
    if user.get('youtube'):
        try:
            yt_result = get_channel_statistics_by_name(user['youtube'])
            if not yt_result or ('Error' in yt_result):
                logging.error(f"YouTube API error: {yt_result.get('Error', 'Unknown error') if yt_result else 'No result'}")
                youtube_stats = {
                    'channel': 'Unavailable',
                    'subscribers': 'Unavailable',
                    'videos': 'Unavailable',
                    'comments': 0,
                    'description': 'Unavailable'
                }
                youtube_logo_url = None
            else:
                youtube_stats = {
                    'channel': yt_result.get('Channel Name', 'Unavailable'),
                    'subscribers': yt_result.get('Subscribers (Actual)', 'Unavailable'),
                    'videos': yt_result.get('Total Videos', 'Unavailable'),
                    'comments': 0,
                    'description': yt_result.get('Description', 'Unavailable')
                }
                youtube_logo_url = None
                try:
                    search_response = youtube.search().list(
                        q=user['youtube'], type='channel', part='snippet', maxResults=1
                    ).execute()
                    if search_response['items']:
                        thumbnails = search_response['items'][0]['snippet'].get('thumbnails', {})
                        youtube_logo_url = thumbnails.get('high', {}).get('url') or thumbnails.get('default', {}).get('url')
                except Exception:
                    youtube_logo_url = None
        except Exception as e:
            logging.error(f"YouTube fetch error: {e}")
            youtube_stats = {
                'channel': 'Unavailable',
                'subscribers': 'Unavailable',
                'videos': 'Unavailable',
                'comments': 0,
                'description': 'Unavailable'
            }
            youtube_logo_url = None
    return render_template('youtube_stats.html', youtube=user.get('youtube'), youtube_stats=youtube_stats, youtube_logo_url=youtube_logo_url)

@app.route('/instagram_stats')
def instagram_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    instagram_stats = None
    instagram_profile_url = None
    if user.get('instagram'):
        try:
            instagram_stats = get_instagram_info(user['instagram'])
            import requests
            ig_username = user['instagram'].strip('@')
            ig_json_url = f"https://www.instagram.com/{ig_username}/?__a=1&__d=dis"
            ig_resp = requests.get(ig_json_url, headers={"User-Agent": "Mozilla/5.0"})
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json()
                instagram_profile_url = ig_data.get('graphql', {}).get('user', {}).get('profile_pic_url_hd', 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png')
            else:
                instagram_profile_url = 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'
        except Exception:
            instagram_stats = None
            instagram_profile_url = 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'
    return render_template('instagram_stats.html', instagram=user.get('instagram'), instagram_stats=instagram_stats, instagram_profile_url=instagram_profile_url)

@app.route('/github_stats')
def github_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    github_stats = None
    github_profile_url = None
    if user.get('github_user') and user.get('github_repo'):
        try:
            github_stats, github_logo, github_error = get_github_info(user['github_user'], user['github_repo'])
            if not github_stats:
                github_stats = {
                    'username': user.get('github_user', 'Unavailable'),
                    'repo': user.get('github_repo', 'Unavailable'),
                    'stars': 'Unavailable',
                    'forks': 'Unavailable',
                    'watchers': 'Unavailable',
                    'description': 'Unavailable',
                    'repo_url': ''
                }
            github_profile_url = github_logo if github_logo else 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
        except Exception:
            github_stats = {
                'username': user.get('github_user', 'Unavailable'),
                'repo': user.get('github_repo', 'Unavailable'),
                'stars': 'Unavailable',
                'forks': 'Unavailable',
                'watchers': 'Unavailable',
                'description': 'Unavailable',
                'repo_url': ''
            }
            github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
    return render_template('github_stats.html', github_user=user.get('github_user'), github_repo=user.get('github_repo'), github_stats=github_stats, github_profile_url=github_profile_url)

@app.route('/reddit_stats')
def reddit_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    reddit_stats = None
    if user.get('reddit'):
        try:
            reddit_stats = get_reddit_info(user['reddit'])
        except Exception:
            reddit_stats = None
    return render_template('reddit_stats.html', reddit=user.get('reddit'), reddit_stats=reddit_stats)

# Route for linking social media accounts
@app.route('/link_accounts', methods=['GET', 'POST'])
def link_accounts():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Get new values from the new form field names
        youtube_channel = request.form.get('youtube_channel') or None
        instagram_username = request.form.get('instagram_username') or None
        reddit_username = request.form.get('reddit_username') or None
        github_username = request.form.get('github_username') or None
        github_repo = request.form.get('github_repo') or None
        update_fields = {}
        if youtube_channel is not None:
            update_fields['youtube'] = youtube_channel
        if instagram_username is not None:
            update_fields['instagram'] = instagram_username
        if reddit_username is not None:
            update_fields['reddit'] = reddit_username
        if github_username is not None:
            update_fields['github_user'] = github_username
        if github_repo is not None:
            update_fields['github_repo'] = github_repo
        if update_fields:
            users.update_one({'username': session['username']}, {'$set': update_fields})
        # After linking, reload the linking page so user can link other accounts
        user = users.find_one({'username': session['username']})
        return render_template('link_accounts.html',
            instagram_username=user.get('instagram', ''),
            youtube_channel=user.get('youtube', ''),
            github_username=user.get('github_user', ''),
            github_repo=user.get('github_repo', ''),
            reddit_username=user.get('reddit', ''))
    # Pass current values to template for better UX
    user = users.find_one({'username': session['username']})
    return render_template('link_accounts.html',
        instagram_username=user.get('instagram', ''),
        youtube_channel=user.get('youtube', ''),
        github_username=user.get('github_user', ''),
        github_repo=user.get('github_repo', ''),
        reddit_username=user.get('reddit', ''))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # For Clerk integration, we just render the login page
    # Clerk handles authentication on the frontend
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # For Clerk integration, we just render the register page
    # Clerk handles registration on the frontend
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Clear any local session data
    session.clear()
    # Redirect to home or login page
    return redirect(url_for('home'))

# Add a route to handle Clerk webhooks (optional)
@app.route('/clerk-webhook', methods=['POST'])
def clerk_webhook():
    # Handle Clerk webhooks here (user creation, deletion, etc.)
    # This is where you'd sync Clerk users with your local database
    return jsonify({'status': 'success'})

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # For Clerk integration, we use the new dashboard template
    # Clerk handles authentication on the frontend
    return render_template('dashboard_clerk.html')

# Individual stats pages
@app.route('/youtube_stats')
                    ).execute()
                    if search_response['items']:
                        thumbnails = search_response['items'][0]['snippet'].get('thumbnails', {})
                        youtube_logo_url = thumbnails.get('high', {}).get('url') or thumbnails.get('default', {}).get('url')
                except Exception:
                    youtube_logo_url = None
        except Exception as e:
            logging.error(f"YouTube fetch error: {e}")
            youtube_stats = {
                'channel': 'Unavailable',
                'subscribers': 'Unavailable',
                'videos': 'Unavailable',
                'comments': 0,
                'description': 'Unavailable'
            }
            youtube_logo_url = None

    # Twitter & Facebook: use form input if POST, else user's linked accounts
    from twitter_utils import get_twitter_info
    from facebook_api_demo import get_facebook_page_stats
    twitter_handle = user.get('twitter', '')
    facebook_page = user.get('facebook', '')
    if request.method == 'POST':
        twitter_handle = request.form.get('twitter_handle', '').strip()
        facebook_page = request.form.get('facebook_page', '').strip()
    twitter_stats = get_twitter_info(twitter_handle) if twitter_handle else {
        'followers': 'Unavailable', 'posts': 'Unavailable', 'engagement_rate': 'Unavailable'
    }
    facebook_stats_raw = get_facebook_page_stats(facebook_page) if facebook_page else {}
    facebook_stats = {
        'followers': facebook_stats_raw.get('followers_count', 'Unavailable'),
        'posts': facebook_stats_raw.get('posts', 'Unavailable'),
        'engagement_rate': facebook_stats_raw.get('engagement_rate', 'Unavailable')
    }

    # GitHub
    if user.get('github_user') and user.get('github_repo'):
        try:
            github_stats, github_logo, github_error = get_github_info(user['github_user'], user['github_repo'])
            if not github_stats:
                github_stats = {
                    'username': user.get('github_user', 'Unavailable'),
                    'repo': user.get('github_repo', 'Unavailable'),
                    'stars': 'Unavailable',
                    'forks': 'Unavailable',
                    'watchers': 'Unavailable',
                    'description': 'Unavailable',
                    'repo_url': ''
                }
            github_profile_url = github_logo if github_logo else 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
        except Exception:
            github_stats = {
                'username': user.get('github_user', 'Unavailable'),
                'repo': user.get('github_repo', 'Unavailable'),
                'stars': 'Unavailable',
                'forks': 'Unavailable',
                'watchers': 'Unavailable',
                'description': 'Unavailable',
                'repo_url': ''
            }
            github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'

    # Reddit
    if user.get('reddit'):
        try:
            reddit_stats = get_reddit_info(user['reddit'])
        except Exception:
            reddit_stats = None

    # Analytics summary (only real API data, no mock values)
    # Calculate total followers (YouTube + Instagram)
    yt_followers = 0
    ig_followers = 0
    if youtube_stats and str(youtube_stats.get('subscribers', '0')).replace(',', '').isdigit():
        yt_followers = int(str(youtube_stats.get('subscribers', '0')).replace(',', ''))
    if instagram_stats and str(instagram_stats.get('followers', '0')).replace(',', '').isdigit():
        ig_followers = int(str(instagram_stats.get('followers', '0')).replace(',', ''))
    total_followers = yt_followers + ig_followers

    # Fetch comments on latest YouTube video
    latest_video_comments = 0
    try:
        if user.get('youtube'):
            # Use YouTube Data API to get latest video and its comment count
            from googleapiclient.discovery import build
            api_key = 'AIzaSyCZqIQAlWGA6brTJc6O79aW-arxN15_dRk'  # Replace with your actual API key
            youtube_api = build('youtube', 'v3', developerKey=api_key)
            # Get channel ID
            search_response = youtube_api.search().list(q=user['youtube'], type='channel', part='snippet', maxResults=1).execute()
            channel_id = None
            if search_response['items']:
                channel_id = search_response['items'][0]['snippet']['channelId']
            if channel_id:
                # Get latest video
                videos_response = youtube_api.search().list(channelId=channel_id, part='id', order='date', maxResults=1, type='video').execute()
                if videos_response['items']:
                    video_id = videos_response['items'][0]['id']['videoId']
                    video_response = youtube_api.videos().list(id=video_id, part='statistics').execute()
                    if video_response['items']:
                        latest_video_comments = int(video_response['items'][0]['statistics'].get('commentCount', 0))
    except Exception:
        latest_video_comments = 0

    analytics = {
        'total_followers': total_followers,
        'followers_growth': '',
        'total_reach': total_followers,
        'reach_growth': '',
        'latest_video_comments': latest_video_comments,
        'engagement_rate': '',
        'engagement_drop': '',
        'total_posts': sum([int(x) for x in [
            twitter_stats.get('posts', 0),
            instagram_stats.get('posts', 0) if instagram_stats else 0,
            facebook_stats.get('posts', 0)
        ] if str(x).isdigit()]),
        'posts_growth': '',
        'mentions_today': '',
        'new_followers': '',
        'comments': youtube_stats.get('comments', 0) if youtube_stats else 0,
        'shares': ''
    }

    # Top posts: leave empty until real API integration
    top_posts = []

    instagram_followers = None
    if instagram_stats and 'followers' in instagram_stats:
        instagram_followers = instagram_stats['followers']
    return render_template('dashboard.html', username=session['username'],
        instagram=user.get('instagram'), instagram_stats=instagram_stats, instagram_profile_url=instagram_profile_url,
        instagram_followers=instagram_followers,
        youtube=user.get('youtube'), youtube_stats=youtube_stats, youtube_logo_url=youtube_logo_url,
        github_user=user.get('github_user'), github_repo=user.get('github_repo'), github_stats=github_stats, github_profile_url=github_profile_url,
        reddit=user.get('reddit'), reddit_stats=reddit_stats,
        twitter_stats=twitter_stats, facebook_stats=facebook_stats,
        analytics=analytics, top_posts=top_posts)
from facebook_utils import get_reddit_info
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright
from sklearn.linear_model import LinearRegression
import numpy as np
import re
import requests

# -------------------------------
# � GitHub Info Fetching
def get_github_info(username, repo):
    user_url = f"https://api.github.com/users/{username}"
    repo_url = f"https://api.github.com/repos/{username}/{repo}"
    user_resp = requests.get(user_url)
    repo_resp = requests.get(repo_url)
    if user_resp.status_code != 200 or repo_resp.status_code != 200:
        error_msg = f"User status: {user_resp.status_code}, Repo status: {repo_resp.status_code}"
        try:
            error_msg += f" | User: {user_resp.json().get('message', '')} | Repo: {repo_resp.json().get('message', '')}"
        except Exception:
            pass
        return None, None, error_msg
    user_data = user_resp.json()
    repo_data = repo_resp.json()
    stats = {
        "username": username,
        "repo": repo,
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "watchers": repo_data.get("watchers_count", 0),
        "description": repo_data.get("description", ""),
        "repo_url": repo_data.get("html_url", "")
    }
    profile_url = user_data.get("avatar_url", "")
    return stats, profile_url, None
# �🔑 YouTube API Setup
# -------------------------------
API_KEY = 'AIzaSyCZqIQAlWGA6brTJc6O79aW-arxN15_dRk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

# -------------------------------
# 🤖 YouTube ML Model Training (Dummy Data)
# -------------------------------
X_train = np.array([
    [100, 1_000_000],
    [200, 3_000_000],
    [300, 5_000_000],
    [400, 8_000_000],
    [500, 10_000_000],
    [600, 13_000_000],
])
y_train = np.array([20000, 50000, 80000, 120000, 150000, 180000])
ml_model = LinearRegression()
ml_model.fit(X_train, y_train)

# -------------------------------
# 🤖 Instagram ML Model Training (Dummy Data)
# -------------------------------
X_ig = np.array([
    [10, 50],
    [50, 100],
    [100, 150],
    [150, 200],
    [200, 300],
    [300, 400]
])
y_ig = np.array([500, 2500, 5000, 9000, 15000, 25000])
ig_model = LinearRegression()
ig_model.fit(X_ig, y_ig)

# -------------------------------
# 📸 Instagram Info Fetching + ML
# -------------------------------
def get_instagram_info(username, use_ml=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0 Safari/537.36"
        ))
        page = context.new_page()

        url = f"https://www.instagram.com/{username.strip('@')}/"
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(6000)


            bio = page.locator('meta[name="description"]').get_attribute("content")
            bio_text = bio.strip() if bio else "Unavailable"

            # Parse followers and posts from bio_text
            followers_match = re.search(r"([\d.,]+)\s*[mMkK]?\s*Followers", bio_text, re.IGNORECASE)
            posts_match = re.search(r"([\d.,]+)\s*[mMkK]?\s*Posts", bio_text, re.IGNORECASE)

            followers = followers_match.group(1) if followers_match else "Unavailable"
            posts = posts_match.group(1) if posts_match else "Unavailable"
            try:
                post_count = int(posts.replace(",", "")) if posts != "Unavailable" else 0
            except Exception:
                post_count = 0

            # Extract only the actual bio text (after the dash)
            actual_bio = "Unavailable"
            if bio_text != "Unavailable":
                dash_split = bio_text.split(" - ", 1)
                if len(dash_split) == 2:
                    actual_bio = dash_split[1].strip()
                else:
                    actual_bio = bio_text.strip()

            bio_length = len(actual_bio) if actual_bio != "Unavailable" else 0

            result = {
                "followers": followers,
                "posts": str(post_count),
                "bio": actual_bio
            }

            if use_ml and actual_bio != "Unavailable":
                predicted = int(ig_model.predict([[post_count, bio_length]])[0])
                result["predicted_followers"] = predicted

            return result

        except Exception as e:
            print("Error:", e)
        finally:
            browser.close()

        return {
            "followers": "Unavailable",
            "posts": "Unavailable",
            "bio": "Unavailable"
        }

# -------------------------------
# 📊 YouTube Stats + ML Prediction
# -------------------------------
def get_channel_statistics_by_name(channel_name, use_ml=False):
    try:
        search_response = youtube.search().list(
            q=channel_name,
            type='channel',
            part='snippet',
            maxResults=1
        ).execute()

        if not search_response['items']:
            return None

        channel_id = search_response['items'][0]['snippet']['channelId']

        stats_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()

        channel_data = stats_response['items'][0]
        snippet = channel_data['snippet']
        stats = channel_data['statistics']

        total_views = int(stats.get('viewCount', 0))
        total_videos = int(stats.get('videoCount', 0))
        actual_subs = int(stats.get('subscriberCount', 0))

        result = {
            'Channel Name': snippet.get('title'),
            'Description': snippet.get('description'),
            'Subscribers (Actual)': actual_subs,
            'Total Views': total_views,
            'Total Videos': total_videos
        }

        if use_ml:
            predicted_subs = int(ml_model.predict([[total_videos, total_views]])[0])
            result['Predicted Subscribers (ML)'] = predicted_subs

        return result

    except Exception as e:
        return {"Error": str(e)}

# -------------------------------
# 🔐 Auth & Routing
# -------------------------------

# Home page route
@app.route('/')
def home():
    # Fetch up to 4 recent reviews, sorted by most recent (_id desc)
    top_reviews = list(reviews.find().sort([('_id', -1)]).limit(4))
    # Add avatar_url for each review
    for review in top_reviews:
        name = review.get('name', 'User')
        review['avatar_url'] = review.get('avatar_url') or f"https://api.dicebear.com/7.x/identicon/svg?seed={name}"
        # Format date if present
        if 'date' in review:
            review['date'] = str(review['date'])
        else:
            review['date'] = ''
        # Add default values for missing fields
        review['role'] = review.get('role', 'User')
        review['title'] = review.get('title', 'Great experience!')
        review['text'] = review.get('text', '')
        review['stars'] = int(review.get('stars', 5))
    return render_template('home.html', top_reviews=top_reviews)




@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
