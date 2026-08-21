import os
import urllib.parse
import datetime
import pytz
import requests
from django.http import JsonResponse
from google import genai
from supabase import create_client, Client

# Environment Secrets
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CRON_SECRET = os.getenv("CRON_SECRET", "my-secret-passkey")

# API Clients
gemini_client = genai.Client()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url else None

TARGET_ACCOUNTS = ["fabrizioromano", "TrollFootball"]

def is_active_window() -> bool:
    """Checks European football hours (11:00 AM - 11:00 PM UK Time)."""
    uk_tz = pytz.timezone("Europe/London")
    now_uk = datetime.datetime.now(uk_tz)
    return 11 <= now_uk.hour < 23

def is_tweet_processed(tweet_id: str) -> bool:
    if not supabase:
        return False
    try:
        res = supabase.table("processed_tweets").select("id").eq("tweet_id", tweet_id).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"Supabase check error: {e}")
        return False

def mark_tweet_processed(tweet_id: str):
    if not supabase:
        return
    try:
        supabase.table("processed_tweets").insert({"tweet_id": tweet_id}).execute()
    except Exception as e:
        print(f"Supabase write error: {e}")

def fetch_latest_tweet(username: str):
    url = f"https://api.twitterapi.io/twitter/user/last_tweet?username={username}"
    headers = {"X-API-Key": TWITTER_API_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Handle nested payload variations from TwitterAPI.io
            tweet_obj = data.get("tweet") or data.get("data") or data
            return tweet_obj
    except Exception as e:
        print(f"Fetch error for @{username}: {e}")
    return None
def generate_ai_banter(tweet_text: str) -> str:
    prompt = (
        "You are a funny, cynical Football Twitter meme account. Write a short, "
        "viral-worthy reply (under 120 characters) to this tweet. "
        "Use modern football slang (cooked, finished, ghost, 😭, 💀) organically. "
        f"Do not sound like an AI. Tweet text: '{tweet_text}'"
    )
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip().replace('"', '')
    except Exception as e:
        print(f"Gemini error: {e}")
        return "Todd Boehly is running a daycare center not a football club 😭💀"

def send_telegram_approval(username: str, original_tweet: str, ai_reply: str, tweet_id: str):
    encoded_reply = urllib.parse.quote(ai_reply)
    x_intent_url = f"https://twitter.com/intent/tweet?text={encoded_reply}&in_reply_to={tweet_id}"
    
    msg = (
        f"🚨 *NEW TWEET SNIPED*\n"
        f"**From:** @{username}\n"
        f"**Tweet:** _{original_tweet}_\n\n"
        f"🤖 *AI Suggested Reply:* \n"
        f"`{ai_reply}`\n\n"
        f"👉 [APPROVE & REPLY ON X]({x_intent_url})"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=5)

def trigger_snipe_view(request):
    """
    HTTP Endpoint to trigger a snipe pass.
    Usage: GET /api/trigger/?key=my-secret-passkey
    """
    key = request.GET.get("key")
    if key != CRON_SECRET:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    # Optional: Skip check if outside peak window
    if not is_active_window() and not request.GET.get("force"):
        return JsonResponse({"status": "skipped", "reason": "Outside active match window"})

    results = []
    for username in TARGET_ACCOUNTS:
        tweet = fetch_latest_tweet(username)
        if tweet:
            tweet_id = str(
                        tweet.get("id_str") or 
                        tweet.get("id") or 
                        tweet.get("tweet_id") or 
                        ""
                    )
            tweet_text = tweet.get("text") or tweet.get("full_text") or ""
            
            if not is_tweet_processed(tweet_id):
                ai_reply = generate_ai_banter(tweet_text)
                send_telegram_approval(username, tweet_text, ai_reply, tweet_id)
                mark_tweet_processed(tweet_id)
                results.append({"account": username, "status": "sniped", "tweet_id": tweet_id})
            else:
                results.append({"account": username, "status": "already_processed", "tweet_id": tweet_id})
        else:
            results.append({"account": username, "status": "no_tweet_found"})

    return JsonResponse({
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "results": results
    })

def health_check(request):
    return JsonResponse({"status": "healthy", "service": "Football Tweet Sniper API"})