import requests
import json

def get_reddit_info(subreddit):
    # Fetch subreddit stats from Reddit public API
    url = f"https://www.reddit.com/r/{subreddit.strip()}/about.json"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SocifyBot/1.0)"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print("Reddit API error:", response.text)
            return {
                "subscribers": "Unavailable",
                "active_users": "Unavailable",
                "description": "Unavailable"
            }
        data = response.json()["data"]
        subscribers = data.get("subscribers", "Unavailable")
        active_users = data.get("accounts_active", "Unavailable")
        description = data.get("public_description", "Unavailable")
        return {
            "subscribers": subscribers,
            "active_users": active_users,
            "description": description
        }
    except Exception as e:
        print("Error:", e)
        return {
            "subscribers": "Unavailable",
            "active_users": "Unavailable",
            "description": "Unavailable"
        }


