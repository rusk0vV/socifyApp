import requests

def get_facebook_page_stats(page_name):
    ACCESS_TOKEN = "EAAJeZBXTPO2kBPD0c7S5Ob5PzHZCzsiXeeKaBP4QjcIaTNdZBWtWOhZA2e5dC4Y82xC0vHjX3kr6uvMwX1Vu68ZAzp5pfXIn3BHZBjSWrwjC12f992dZB2vwVudI47ZCQB2FIaweNO1pv4z2v5A4ISxPlVoxxQpazPXyS6msswF2uWsyZCJq25yFB6YQa9VU5r5HF2QZDZD"
    url = f"https://graph.facebook.com/v19.0/{page_name}?fields=followers_count,about,name&access_token={ACCESS_TOKEN}"
    try:
        response = requests.get(url)
        data = response.json()
        return data
    except Exception as e:
        print("Error:", e)
        return {"error": str(e)}
