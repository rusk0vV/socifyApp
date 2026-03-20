import requests
from bs4 import BeautifulSoup
import re

def get_twitter_info(username):
    url = f"https://twitter.com/{username.strip('@')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {
                "followers": "Unavailable",
                "following": "Unavailable",
                "posts": "Unavailable",
                "likes": "Unavailable",
                "replies": "Unavailable",
                "bio": "Unavailable"
            }
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Try to extract bio from meta tag
        bio = "Unavailable"
        meta_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_tag and meta_tag.get('content'):
            bio = meta_tag['content']

        # Try to extract stats from embedded JSON
        followers = "Unavailable"
        following = "Unavailable"
        posts = "Unavailable"
        likes = "Unavailable"
        replies = "Unavailable"

        # Twitter embeds a JSON with user stats in the HTML
        import json
        user_json = None
        for script in soup.find_all('script'):
            if script.string and 'followers_count' in script.string:
                try:
                    json_text = script.string
                    # Find the first { ... } block
                    start = json_text.find('{')
                    end = json_text.rfind('}') + 1
                    if start != -1 and end != -1:
                        json_block = json_text[start:end]
                        data = json.loads(json_block)
                        # Traverse to user stats if possible
                        if 'followers_count' in data:
                            followers = str(data.get('followers_count', 'Unavailable'))
                        if 'friends_count' in data:
                            following = str(data.get('friends_count', 'Unavailable'))
                        if 'statuses_count' in data:
                            posts = str(data.get('statuses_count', 'Unavailable'))
                        break
                except Exception:
                    continue

        # Fallback to meta tag parsing if JSON not found
        if followers == "Unavailable" and bio != "Unavailable":
            followers_match = re.search(r"([\d,.]+) Followers", bio)
            if followers_match:
                followers = followers_match.group(1)
        if following == "Unavailable" and bio != "Unavailable":
            following_match = re.search(r"([\d,.]+) Following", bio)
            if following_match:
                following = following_match.group(1)
        if posts == "Unavailable" and bio != "Unavailable":
            posts_match = re.search(r"([\d,.]+) Tweets", bio)
            if posts_match:
                posts = posts_match.group(1)

        return {
            "followers": followers,
            "following": following,
            "posts": posts,
            "likes": likes,
            "replies": replies,
            "bio": bio
        }
    except Exception as e:
        print("Error:", e)
        return {
            "followers": "Unavailable",
            "following": "Unavailable",
            "posts": "Unavailable",
            "likes": "Unavailable",
            "replies": "Unavailable",
            "bio": "Unavailable"
        }
