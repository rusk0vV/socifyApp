import logging
import os
import random
import re
from datetime import datetime

import numpy as np
import requests
from flask import Flask, redirect, render_template, request, session, url_for
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from sklearn.linear_model import LinearRegression
from werkzeug.security import check_password_hash, generate_password_hash

from facebook_api_demo import get_facebook_page_stats
from facebook_utils import get_reddit_info
from ml import predict_views
from twitter_utils import get_twitter_info

# -------------------------------
# App & Database Configuration
# -------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

client = MongoClient('mongodb://localhost:27017/')
db = client['socioapp']
users = db['users']
reviews_collection = db['reviews']

# -------------------------------
# YouTube API Setup (Single Source of Truth)
# Paste your YouTube Data API v3 key below or set YOUTUBE_API_KEY in environment
# -------------------------------
API_KEY = os.environ.get('YOUTUBE_API_KEY', 'AIzaSyBzC1__-x3PoHV6MyT8yYX1h-pEBLn_PF4')
youtube = build('youtube', 'v3', developerKey=API_KEY)


# Jinja2 filter for formatting follower counts
def format_followers(value):
    try:
        value = float(value)
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        else:
            return str(int(value))
    except Exception:
        return str(value)


app.jinja_env.filters['format_followers'] = format_followers

# -------------------------------
# YouTube ML Model Training (Dummy Data)
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
# Instagram ML Model Training (Dummy Data)
# -------------------------------
X_ig = np.array([
    [10, 50],
    [50, 100],
    [100, 150],
    [150, 200],
    [200, 300],
    [300, 400],
])
y_ig = np.array([500, 2500, 5000, 9000, 15000, 25000])
ig_model = LinearRegression()
ig_model.fit(X_ig, y_ig)


# -------------------------------
# GitHub Info Fetching
# -------------------------------
def get_github_info(username, repo):
    user_url = f"https://api.github.com/users/{username}"
    repo_url = f"https://api.github.com/repos/{username}/{repo}"
    user_resp = requests.get(user_url, timeout=15)
    repo_resp = requests.get(repo_url, timeout=15)
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
        "repo_url": repo_data.get("html_url", ""),
    }
    profile_url = user_data.get("avatar_url", "")
    return stats, profile_url, None


# -------------------------------
# Instagram Info Fetching + ML
# -------------------------------
def get_instagram_info(username, use_ml=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0 Safari/537.36"
            )
        )
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
                "bio": actual_bio,
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
            "bio": "Unavailable",
        }


# -------------------------------
# YouTube Stats + ML Prediction
# -------------------------------
def get_comprehensive_youtube_stats(channel_name):
    try:
        # Search for channel and get channelId in one call
        search_response = youtube.search().list(
            q=channel_name,
            type='channel',
            part='id',
            maxResults=1,
        ).execute()

        if not search_response.get('items'):
            return {"Error": "Channel not found"}

        channel_id = search_response['items'][0]['id']['channelId']

        # Get only needed channel data
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id,
        ).execute()

        if not channel_response.get('items'):
            return {"Error": "Channel data not found"}

        channel_data = channel_response['items'][0]
        snippet = channel_data['snippet']
        stats = channel_data['statistics']
        status = channel_data.get('status', {})
        branding = channel_data.get('brandingSettings', {})

        # Get recent videos (3 for display)
        recent_videos = []
        latest_video_comments_list = []
        try:
            videos_response = youtube.search().list(
                channelId=channel_id,
                part='id',
                type='video',
                order='date',
                maxResults=3,
            ).execute()

            video_ids = [item['id']['videoId'] for item in videos_response.get('items', [])]

            if video_ids:
                # Get all needed video details in one call
                video_details = youtube.videos().list(
                    part='snippet,statistics',
                    id=','.join(video_ids),
                ).execute()

                for idx, video in enumerate(video_details.get('items', [])):
                    video_snippet = video['snippet']
                    video_stats = video.get('statistics', {})
                    recent_videos.append({
                        'title': video_snippet.get('title', ''),
                        'thumbnail': video_snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                        'views': int(video_stats.get('viewCount', 0)),
                        'likes': int(video_stats.get('likeCount', 0)),
                        'comments': int(video_stats.get('commentCount', 0)),
                        'published_date': video_snippet.get('publishedAt', '').split('T')[0] if video_snippet.get('publishedAt') else '',
                    })
                    # For the first (latest) video, fetch up to 5 recent comments
                    if idx == 0:
                        latest_video_id = video['id']
                        try:
                            comments_response = youtube.commentThreads().list(
                                part='snippet',
                                videoId=latest_video_id,
                                maxResults=5,
                                order='time',
                            ).execute()
                            for item in comments_response.get('items', []):
                                top_comment = item['snippet']['topLevelComment']['snippet']
                                latest_video_comments_list.append({
                                    'author': top_comment.get('authorDisplayName', 'Unknown'),
                                    'text': top_comment.get('textDisplay', ''),
                                    'published_at': top_comment.get('publishedAt', '').split('T')[0] if top_comment.get('publishedAt') else '',
                                    'author_profile_image': top_comment.get('authorProfileImageUrl', ''),
                                })
                        except Exception as e:
                            print(f"Error fetching comments: {e}")
        except Exception as e:
            print(f"Error fetching recent videos: {e}")

        # Get top videos by views
        top_videos = []
        try:
            top_videos_response = youtube.search().list(
                channelId=channel_id,
                part='snippet',
                type='video',
                order='viewCount',
                maxResults=5,
            ).execute()

            top_video_ids = [item['id']['videoId'] for item in top_videos_response.get('items', [])]

            if top_video_ids:
                top_video_details = youtube.videos().list(
                    part='statistics,snippet',
                    id=','.join(top_video_ids),
                ).execute()

                for video in top_video_details.get('items', []):
                    video_snippet = video['snippet']
                    video_stats = video.get('statistics', {})
                    top_videos.append({
                        'title': video_snippet.get('title', ''),
                        'thumbnail': video_snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                        'views': int(video_stats.get('viewCount', 0)),
                        'likes': int(video_stats.get('likeCount', 0)),
                        'comments': int(video_stats.get('commentCount', 0)),
                        'published_date': video_snippet.get('publishedAt', '').split('T')[0] if video_snippet.get('publishedAt') else '',
                    })
        except Exception as e:
            print(f"Error fetching top videos: {e}")

        # Get playlists count
        playlists_count = 0
        try:
            playlists_response = youtube.playlists().list(
                channelId=channel_id,
                part='snippet',
                maxResults=50,
            ).execute()
            playlists_count = playlists_response.get('pageInfo', {}).get('totalResults', 0)
        except Exception as e:
            print(f"Error fetching playlists: {e}")

        # Calculate total comments across recent videos
        total_comments = 0
        try:
            all_videos_response = youtube.search().list(
                channelId=channel_id,
                part='id',
                type='video',
                order='date',
                maxResults=50,
            ).execute()

            all_video_ids = [item['id']['videoId'] for item in all_videos_response.get('items', [])]

            if all_video_ids:
                all_video_details = youtube.videos().list(
                    part='statistics',
                    id=','.join(all_video_ids),
                ).execute()

                for video in all_video_details.get('items', []):
                    video_stats = video.get('statistics', {})
                    comment_count = int(video_stats.get('commentCount', 0))
                    total_comments += comment_count
        except Exception as e:
            print(f"Error fetching total comments: {e}")
            total_comments = 0

        # Process keywords
        keywords = []
        if branding.get('channel', {}).get('keywords'):
            keywords = branding['channel']['keywords'].split(',')
            keywords = [keyword.strip() for keyword in keywords[:10]]

        # Parse creation date
        created_date = snippet.get('publishedAt', '').split('T')[0] if snippet.get('publishedAt') else ''

        result = {
            'channel': snippet.get('title', ''),
            'description': snippet.get('description', '')[:300] + '...' if len(snippet.get('description', '')) > 300 else snippet.get('description', ''),
            'created_date': created_date,
            'country': snippet.get('country', ''),
            'profile_image': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'banner_url': branding.get('image', {}).get('bannerExternalUrl', ''),
            'subscribers': int(stats.get('subscriberCount', 0)),
            'videos': int(stats.get('videoCount', 0)),
            'total_views': int(stats.get('viewCount', 0)),
            'total_comments': total_comments,
            'playlists': playlists_count,
            'keywords': keywords,
            'custom_url': snippet.get('customUrl', ''),
            'privacy_status': status.get('privacyStatus', 'public'),
            'default_language': snippet.get('defaultLanguage', ''),
            'recent_videos': recent_videos,
            'top_videos': top_videos,
            'latest_video_comments_list': latest_video_comments_list,
            'latest_video_views': recent_videos[0]['views'] if recent_videos else 0,
            'latest_video_likes': recent_videos[0]['likes'] if recent_videos else 0,
            'latest_video_comments': recent_videos[0]['comments'] if recent_videos else 0,
            'second_latest_video_views': recent_videos[1]['views'] if len(recent_videos) > 1 else 0,
            'second_latest_video_likes': recent_videos[1]['likes'] if len(recent_videos) > 1 else 0,
            'second_latest_video_comments': recent_videos[1]['comments'] if len(recent_videos) > 1 else 0,
        }

        return result

    except Exception as e:
        return {"Error": str(e)}


# Legacy function for backward compatibility
def get_channel_statistics_by_name(channel_name, use_ml=False):
    try:
        search_response = youtube.search().list(
            q=channel_name,
            type='channel',
            part='snippet',
            maxResults=1,
        ).execute()

        if not search_response.get('items'):
            return None

        channel_id = search_response['items'][0]['snippet']['channelId']

        stats_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id,
        ).execute()

        channel_data = stats_response['items'][0]
        snippet = channel_data['snippet']
        stats = channel_data['statistics']

        total_views = int(stats.get('viewCount', 0))
        total_videos = int(stats.get('videoCount', 0))
        actual_subs = int(stats.get('subscriberCount', 0))

        result = {
            'Description': snippet.get('description'),
            'Subscribers (Actual)': actual_subs,
            'Total Views': total_views,
            'Total Videos': total_videos,
        }

        if use_ml:
            predicted_subs = int(ml_model.predict([[total_videos, total_views]])[0])
            result['Predicted Subscribers (ML)'] = predicted_subs

        return result

    except Exception as e:
        return {"Error": str(e)}


# -------------------------------
# Routes
# -------------------------------
@app.route('/review', methods=['GET', 'POST'])
def review():
    if request.method == 'POST':
        name = request.form.get('name')
        role = request.form.get('role')
        title = request.form.get('title')
        text = request.form.get('text')
        stars = int(request.form.get('stars', 5))

        avatar_styles = ['avataaars', 'identicon', 'initials', 'bottts', 'gridy', 'micah']
        random_style = random.choice(avatar_styles)
        random_seed = f"{name}{random.randint(1000, 9999)}"
        avatar_url = f"https://api.dicebear.com/7.x/{random_style}/svg?seed={random_seed}"

        review_doc = {
            'name': name,
            'role': role,
            'title': title,
            'text': text,
            'stars': stars,
            'avatar_url': avatar_url,
            'date': datetime.now().strftime('%Y-%m-%d'),
        }
        reviews_collection.insert_one(review_doc)
        return redirect(url_for('reviews'))
    return render_template('review.html')


@app.route('/reviews')
def reviews():
    top_reviews = list(reviews_collection.find().sort([('_id', -1)]).limit(4))
    for rev in top_reviews:
        name = rev.get('name', 'User')
        rev['avatar_url'] = rev.get('avatar_url') or f"https://api.dicebear.com/7.x/identicon/svg?seed={name}"
        rev['role'] = rev.get('role', 'User')
        rev['title'] = rev.get('title', 'Great experience!')
        rev['text'] = rev.get('text', '')
        rev['stars'] = int(rev.get('stars', 5))
        rev['date'] = str(rev.get('date', ''))
    return render_template('reviews.html', top_reviews=top_reviews)


@app.route('/youtube_stats')
def youtube_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    youtube_stats = {}
    predicted_views = None

    if user.get('youtube'):
        try:
            yt_result = get_comprehensive_youtube_stats(user['youtube'])
            if yt_result and 'Error' not in yt_result:
                youtube_stats = yt_result
                if youtube_stats.get('subscribers'):
                    try:
                        predicted_views = predict_views(youtube_stats['subscribers'])
                        if predicted_views >= 1_000_000:
                            predicted_views = f"{predicted_views / 1_000_000:.1f}M"
                        elif predicted_views >= 1_000:
                            predicted_views = f"{predicted_views / 1_000:.1f}K"
                        else:
                            predicted_views = f"{int(predicted_views)}"
                    except Exception as ml_error:
                        print(f"ML prediction error: {ml_error}")
                        predicted_views = "N/A"
            else:
                youtube_stats = yt_result
        except Exception as e:
            print(f"YouTube API error: {e}")
            youtube_stats = {'channel': 'Error Loading Data', 'description': f'Error: {str(e)}'}
    else:
        youtube_stats = {'channel': 'No YouTube Channel Linked', 'description': 'Please link your YouTube channel in account settings.'}

    return render_template('youtube_stats.html', youtube_stats=youtube_stats, predicted_views=predicted_views)


@app.route('/my_videos')
def my_videos():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    videos = []
    if user.get('youtube'):
        try:
            yt_result = get_comprehensive_youtube_stats(user['youtube'])
            if yt_result and 'Error' not in yt_result:
                videos = yt_result.get('recent_videos', [])
            else:
                videos = []
        except Exception as e:
            print(f"YouTube API error: {e}")
            videos = []
    return render_template('my_videos.html', videos=videos)


@app.route('/instagram_stats')
def instagram_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    instagram_stats = None
    instagram_profile_url = None
    if user.get('instagram'):
        try:
            instagram_stats = get_instagram_info(user['instagram'])
            ig_username = user['instagram'].strip('@')
            ig_json_url = f"https://www.instagram.com/{ig_username}/?__a=1&__d=dis"
            ig_resp = requests.get(ig_json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json()
                instagram_profile_url = ig_data.get('graphql', {}).get('user', {}).get(
                    'profile_pic_url_hd',
                    'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png',
                )
            else:
                instagram_profile_url = 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'
        except Exception:
            instagram_stats = None
            instagram_profile_url = 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'
    return render_template(
        'instagram_stats.html',
        instagram=user.get('instagram'),
        instagram_stats=instagram_stats,
        instagram_profile_url=instagram_profile_url,
    )


@app.route('/github_stats')
def github_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    github_stats = None
    github_profile_url = None
    if user.get('github_user') and user.get('github_repo'):
        try:
            github_stats, github_logo, _ = get_github_info(user['github_user'], user['github_repo'])
            if not github_stats:
                github_stats = {
                    'username': user.get('github_user', 'Unavailable'),
                    'repo': user.get('github_repo', 'Unavailable'),
                    'stars': 'Unavailable',
                    'forks': 'Unavailable',
                    'watchers': 'Unavailable',
                    'description': 'Unavailable',
                    'repo_url': '',
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
                'repo_url': '',
            }
            github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
    else:
        github_stats = {
            'username': 'Unavailable',
            'repo': 'Unavailable',
            'stars': 'Unavailable',
            'forks': 'Unavailable',
            'watchers': 'Unavailable',
            'description': 'Unavailable',
            'repo_url': '',
        }
        github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
    return render_template(
        'github_stats.html',
        github_user=user.get('github_user'),
        github_repo=user.get('github_repo'),
        github_stats=github_stats,
        github_profile_url=github_profile_url,
    )


@app.route('/reddit_stats')
def reddit_stats_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    reddit_stats = None
    if user.get('reddit'):
        try:
            reddit_stats = get_reddit_info(user['reddit'])
        except Exception:
            reddit_stats = None
    return render_template('reddit_stats.html', reddit=user.get('reddit'), reddit_stats=reddit_stats)


@app.route('/link_accounts', methods=['GET', 'POST'])
def link_accounts():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
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
        user = users.find_one({'username': session['username']}) or {}
        return render_template(
            'link_accounts.html',
            instagram_username=user.get('instagram', ''),
            youtube_channel=user.get('youtube', ''),
            github_username=user.get('github_user', ''),
            github_repo=user.get('github_repo', ''),
            reddit_username=user.get('reddit', ''),
        )

    return render_template(
        'link_accounts.html',
        instagram_username=user.get('instagram', ''),
        youtube_channel=user.get('youtube', ''),
        github_username=user.get('github_user', ''),
        github_repo=user.get('github_repo', ''),
        reddit_username=user.get('reddit', ''),
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if users.find_one({'username': username}):
            error = 'Username already exists'
            return render_template('register.html', error=error)
        hashed_pw = generate_password_hash(password)
        users.insert_one({'username': username, 'email': email, 'password': hashed_pw})
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    instagram_profile_url = None
    instagram_username = None
    instagram_bio = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            try:
                ig_username = user.get('instagram', '').strip('@')
                if ig_username:
                    ig_json_url = f"https://www.instagram.com/{ig_username}/?__a=1&__d=dis"
                    ig_resp = requests.get(ig_json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if ig_resp.status_code == 200:
                        ig_data = ig_resp.json()
                        instagram_profile_url = ig_data.get('graphql', {}).get('user', {}).get('profile_pic_url_hd', None)
                        instagram_username = ig_data.get('graphql', {}).get('user', {}).get('username', None)
                        instagram_bio = ig_data.get('graphql', {}).get('user', {}).get('biography', None)
            except Exception:
                instagram_profile_url = None
                instagram_username = None
                instagram_bio = None
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password.'
    return render_template(
        'login.html',
        error=error,
        instagram_profile_url=instagram_profile_url,
        instagram_username=instagram_username,
        instagram_bio=instagram_bio,
    )


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users.find_one({'username': session['username']})
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    instagram_stats = None
    instagram_profile_url = None
    youtube_stats = None
    youtube_logo_url = None
    github_stats = None
    github_profile_url = None
    reddit_stats = None

    # Instagram
    if user.get('instagram'):
        try:
            instagram_stats = get_instagram_info(user['instagram'])
            ig_username = user['instagram'].strip('@')
            ig_json_url = f"https://www.instagram.com/{ig_username}/?__a=1&__d=dis"
            ig_resp = requests.get(ig_json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json()
                instagram_profile_url = ig_data.get('graphql', {}).get('user', {}).get(
                    'profile_pic_url_hd',
                    'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png',
                )
            else:
                instagram_profile_url = 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'
        except Exception:
            instagram_stats = None
            instagram_profile_url = instagram_profile_url if instagram_profile_url else 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png'

    # YouTube
    if user.get('youtube'):
        try:
            yt_result = get_comprehensive_youtube_stats(user['youtube'])
            if not yt_result or ('Error' in yt_result):
                logging.error(f"YouTube API error: {yt_result.get('Error', 'Unknown error') if yt_result else 'No result'}")
                youtube_stats = {
                    'channel': 'Unavailable',
                    'subscribers': 'Unavailable',
                    'videos': 'Unavailable',
                    'total_comments': 0,
                    'latest_video_comments_list': [],
                    'description': 'Unavailable',
                    'latest_video_views': 0,
                    'latest_video_likes': 0,
                    'latest_video_comments': 0,
                    'second_latest_video_views': 0,
                    'second_latest_video_likes': 0,
                    'second_latest_video_comments': 0,
                    'recent_videos': [],
                }
                youtube_logo_url = None
            else:
                youtube_stats = {
                    'channel': yt_result.get('channel', 'Unavailable'),
                    'subscribers': yt_result.get('subscribers', 'Unavailable'),
                    'videos': yt_result.get('videos', 'Unavailable'),
                    'total_comments': yt_result.get('total_comments', 0),
                    'latest_video_comments_list': yt_result.get('latest_video_comments_list', []),
                    'description': yt_result.get('description', 'Unavailable'),
                    'latest_video_views': yt_result.get('latest_video_views', 0),
                    'latest_video_likes': yt_result.get('latest_video_likes', 0),
                    'latest_video_comments': yt_result.get('latest_video_comments', 0),
                    'second_latest_video_views': yt_result.get('second_latest_video_views', 0),
                    'second_latest_video_likes': yt_result.get('second_latest_video_likes', 0),
                    'second_latest_video_comments': yt_result.get('second_latest_video_comments', 0),
                    'recent_videos': yt_result.get('recent_videos', []),
                }
                youtube_logo_url = yt_result.get('profile_image') or None
        except Exception as e:
            logging.error(f"YouTube fetch error: {e}")
            youtube_stats = {
                'channel': 'Unavailable',
                'subscribers': 'Unavailable',
                'videos': 'Unavailable',
                'total_comments': 0,
                'latest_video_comments_list': [],
                'description': 'Unavailable',
                'latest_video_views': 0,
                'latest_video_likes': 0,
                'latest_video_comments': 0,
                'second_latest_video_views': 0,
                'second_latest_video_likes': 0,
                'second_latest_video_comments': 0,
                'recent_videos': [],
            }
            youtube_logo_url = None

    # Twitter & Facebook
    twitter_handle = user.get('twitter', '')
    facebook_page = user.get('facebook', '')
    if request.method == 'POST':
        twitter_handle = request.form.get('twitter_handle', '').strip()
        facebook_page = request.form.get('facebook_page', '').strip()
    twitter_stats = get_twitter_info(twitter_handle) if twitter_handle else {
        'followers': 'Unavailable',
        'posts': 'Unavailable',
        'engagement_rate': 'Unavailable',
    }
    facebook_stats_raw = get_facebook_page_stats(facebook_page) if facebook_page else {}
    facebook_stats = {
        'followers': facebook_stats_raw.get('followers_count', 'Unavailable'),
        'posts': facebook_stats_raw.get('posts', 'Unavailable'),
        'engagement_rate': facebook_stats_raw.get('engagement_rate', 'Unavailable'),
    }

    # GitHub
    if user.get('github_user') and user.get('github_repo'):
        try:
            github_stats, github_logo, _ = get_github_info(user['github_user'], user['github_repo'])
            if not github_stats:
                github_stats = {
                    'username': user.get('github_user', 'Unavailable'),
                    'repo': user.get('github_repo', 'Unavailable'),
                    'stars': 'Unavailable',
                    'forks': 'Unavailable',
                    'watchers': 'Unavailable',
                    'description': 'Unavailable',
                    'repo_url': '',
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
                'repo_url': '',
            }
            github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
    else:
        github_stats = {
            'username': 'Unavailable',
            'repo': 'Unavailable',
            'stars': 'Unavailable',
            'forks': 'Unavailable',
            'watchers': 'Unavailable',
            'description': 'Unavailable',
            'repo_url': '',
        }
        github_profile_url = 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'

    # Reddit
    if user.get('reddit'):
        try:
            reddit_stats = get_reddit_info(user['reddit'])
        except Exception:
            reddit_stats = None

    # Calculate total followers (YouTube + Instagram)
    yt_followers = 0
    ig_followers = 0
    if youtube_stats and str(youtube_stats.get('subscribers', '0')).replace(',', '').isdigit():
        yt_followers = int(str(youtube_stats.get('subscribers', '0')).replace(',', ''))
    if instagram_stats and str(instagram_stats.get('followers', '0')).replace(',', '').isdigit():
        ig_followers = int(str(instagram_stats.get('followers', '0')).replace(',', ''))
    total_followers = yt_followers + ig_followers

    # Latest video comments (already fetched in youtube_stats)
    latest_video_comments = int(youtube_stats.get('latest_video_comments', 0)) if youtube_stats else 0

    # Calculate engagement ratio for latest YouTube video and comparison
    engagement_ratio = 0
    previous_engagement_ratio = 0
    engagement_difference = 0
    engagement_trend = ""

    if youtube_stats and youtube_stats.get('latest_video_views', 0) > 0:
        latest_likes = youtube_stats.get('latest_video_likes', 0)
        latest_comments = youtube_stats.get('latest_video_comments', 0)
        latest_views = youtube_stats.get('latest_video_views', 0)

        if latest_views > 0:
            engagement_ratio = round(((latest_likes + latest_comments) / latest_views) * 100, 2)

        second_latest_likes = youtube_stats.get('second_latest_video_likes', 0)
        second_latest_comments = youtube_stats.get('second_latest_video_comments', 0)
        second_latest_views = youtube_stats.get('second_latest_video_views', 0)

        if second_latest_views > 0:
            previous_engagement_ratio = round(((second_latest_likes + second_latest_comments) / second_latest_views) * 100, 2)
            engagement_difference = round(engagement_ratio - previous_engagement_ratio, 2)

            if engagement_difference > 0:
                engagement_trend = "increase"
            elif engagement_difference < 0:
                engagement_trend = "decrease"
            else:
                engagement_trend = "stable"

    analytics = {
        'total_followers': total_followers,
        'followers_growth': '',
        'total_reach': total_followers,
        'reach_growth': '',
        'latest_video_comments': latest_video_comments,
        'engagement_rate': engagement_ratio,
        'previous_engagement_rate': previous_engagement_ratio,
        'engagement_difference': engagement_difference,
        'engagement_trend': engagement_trend,
        'engagement_drop': '',
        'total_posts': sum([
            int(x)
            for x in [
                twitter_stats.get('posts', 0),
                instagram_stats.get('posts', 0) if instagram_stats else 0,
                facebook_stats.get('posts', 0),
            ]
            if str(x).isdigit()
        ]),
        'posts_growth': '',
        'mentions_today': '',
        'new_followers': '',
        'comments': youtube_stats.get('total_comments', 0) if youtube_stats else 0,
        'total_comments': youtube_stats.get('total_comments', 0) if youtube_stats else 0,
        'shares': '',
    }

    top_posts = []

    instagram_followers = None
    if instagram_stats and 'followers' in instagram_stats:
        instagram_followers = instagram_stats['followers']

    return render_template(
        'dashboard.html',
        username=session['username'],
        instagram=user.get('instagram'),
        instagram_stats=instagram_stats,
        instagram_profile_url=instagram_profile_url,
        instagram_followers=instagram_followers,
        youtube=user.get('youtube'),
        youtube_stats=youtube_stats,
        youtube_logo_url=youtube_logo_url,
        github_user=user.get('github_user'),
        github_repo=user.get('github_repo'),
        github_stats=github_stats,
        github_profile_url=github_profile_url,
        reddit=user.get('reddit'),
        reddit_stats=reddit_stats,
        twitter_stats=twitter_stats,
        facebook_stats=facebook_stats,
        analytics=analytics,
        top_posts=top_posts,
    )


@app.route('/')
def home():
    top_reviews = list(reviews_collection.find().sort([('_id', -1)]).limit(4))
    for rev in top_reviews:
        name = rev.get('name', 'User')
        rev['avatar_url'] = rev.get('avatar_url') or f"https://api.dicebear.com/7.x/identicon/svg?seed={name}"
        rev['date'] = str(rev.get('date', ''))
        rev['role'] = rev.get('role', 'User')
        rev['title'] = rev.get('title', 'Great experience!')
        rev['text'] = rev.get('text', '')
        rev['stars'] = int(rev.get('stars', 5))
    return render_template('home.html', top_reviews=top_reviews)


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
