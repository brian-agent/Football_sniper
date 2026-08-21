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

TARGET_ACCOUNTS = ["fabrizioromano", "TrollFootball"]

def get_supabase_client():
    """Safely initializes Supabase client without breaking startup imports."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if url and key:
        try:
            return create_client(url, key)
        except Exception as e:
            print(f"Supabase init error: {e}")

    return None


supabase = get_supabase_client()

def is_active_window() -> bool:
    """Checks European football hours (11:00 AM - 11:00 PM UK Time)."""
    uk_tz = pytz.timezone("Europe/London")
    now_uk = datetime.datetime.now(uk_tz)
    return 11 <= now_uk.hour < 23

def is_tweet_processed(tweet_id: str) -> bool:
    """Queries Supabase to verify if tweet ID was already processed."""
    if not supabase or not tweet_id:
        return False
    try:
        res = supabase.table("processed_tweets").select("id").eq("tweet_id", str(tweet_id)).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"Supabase check error: {e}")
        return False

def mark_tweet_processed(tweet_id: str):
    """Saves newly processed tweet ID to Supabase."""
    if not supabase or not tweet_id:
        return
    try:
        supabase.table("processed_tweets").insert({"tweet_id": str(tweet_id)}).execute()
    except Exception as e:
        print(f"Supabase write error: {e}")

def fetch_latest_tweet(username: str):
    """Fetches latest tweet from TwitterAPI.io."""
    url = "https://api.twitterapi.io/twitter/user/last_tweets"

    headers = {
        "X-API-Key": TWITTER_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "userName": username,
    }

    try:
        res = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10,
        )

        print(f"Twitter API @{username}: HTTP {res.status_code}")
        print(f"Twitter API response: {res.text[:2000]}")

        res.raise_for_status()

        response_data = res.json()

        tweets = response_data.get("data", {}).get("tweets", [])

        if not isinstance(tweets, list) or not tweets:
            print(f"No tweets returned for @{username}")
            return None

        latest = tweets[0]

        print(
            f"Found {len(tweets)} tweets for @{username}. "
            f"Latest ID: {latest.get('id')}"
        )

        return latest

    except requests.exceptions.HTTPError as e:
        print(f"Twitter API HTTP error for @{username}: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Twitter API request error for @{username}: {e}")

    except ValueError as e:
        print(f"Twitter API JSON error for @{username}: {e}")

    except Exception as e:
        print(f"Unexpected fetch error for @{username}: {e}")

    return None
def generate_ai_banter(tweet_text: str) -> str:
    """Generates and logs the AI football banter."""
    print("=" * 60)
    print("🤖 GEMINI BANter GENERATION STARTED")
    print(f"📝 Original tweet: {tweet_text}")

    prompt = (
        "You are a funny, cynical Football Twitter meme account. "
        "Write a short, viral-worthy reply under 120 characters. "
        "Use modern football slang (cooked, finished, ghost, 😭, 💀) "
        "organically. Do not sound like an AI. "
        f"Tweet text: '{tweet_text}'"
    )

    print(f"📨 Gemini prompt created")
    print(f"📏 Prompt length: {len(prompt)} characters")

    try:
        print("⏳ Calling Gemini...")

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        print("✅ Gemini API responded")
        print(f"📦 Response object: {response}")

        if not response.text:
            print("❌ Gemini returned empty text")
            return None

        ai_reply = response.text.strip().replace('"', '')

        print(f"🔥 GENERATED BANTER: {ai_reply}")
        print(f"📏 Reply length: {len(ai_reply)} characters")
        print("🤖 GEMINI GENERATION COMPLETE")
        print("=" * 60)

        return ai_reply

    except Exception as e:
        print("❌ GEMINI ERROR")
        print(f"Error type: {type(e).__name__}")
        print(f"Error: {e}")
        print("=" * 60)

        return None
def send_telegram_approval(
    username: str,
    original_tweet: str,
    ai_reply: str,
    tweet_id: str
):
    """Sends Telegram approval message and logs the complete result."""

    print("=" * 60)
    print("📱 TELEGRAM DELIVERY STARTED")
    print(f"👤 Account: @{username}")
    print(f"🐦 Tweet ID: {tweet_id}")
    print(f"🤖 AI Reply: {ai_reply}")

    encoded_reply = urllib.parse.quote(ai_reply)

    x_intent_url = (
        f"https://twitter.com/intent/tweet"
        f"?text={encoded_reply}"
        f"&in_reply_to={tweet_id}"
    )

    msg = (
        f"🚨 *NEW TWEET SNIPED*\n"
        f"*From:* @{username}\n"
        f"*Tweet:* _{original_tweet}_\n\n"
        f"🤖 *AI Suggested Reply:*\n"
        f"`{ai_reply}`\n\n"
        f"👉 [APPROVE & REPLY ON X]({x_intent_url})"
    )

    print("📝 Telegram message constructed")
    print(f"📏 Message length: {len(msg)} characters")
    print(f"🔗 X reply URL: {x_intent_url}")

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    print(f"🎯 Telegram chat ID configured: {bool(TELEGRAM_CHAT_ID)}")
    print(f"🔑 Telegram bot token configured: {bool(TELEGRAM_BOT_TOKEN)}")
    print("⏳ Sending request to Telegram...")

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10,
        )

        print(f"📡 Telegram HTTP status: {response.status_code}")
        print(f"📦 Telegram raw response: {response.text}")

        if response.status_code != 200:
            print("❌ TELEGRAM HTTP ERROR")
            return False

        telegram_data = response.json()

        if telegram_data.get("ok") is True:
            print("✅ TELEGRAM MESSAGE DELIVERED")
            print(f"📨 Telegram message ID: "
                  f"{telegram_data.get('result', {}).get('message_id')}")
            print("=" * 60)
            return True

        print("❌ TELEGRAM API REJECTED MESSAGE")
        print(f"Telegram response: {telegram_data}")
        print("=" * 60)

        return False

    except Exception as e:
        print("❌ TELEGRAM REQUEST ERROR")
        print(f"Error type: {type(e).__name__}")
        print(f"Error: {e}")
        print("=" * 60)

        return False
def test_telegram_bot():
    print("=" * 60)
    print("🔎 TESTING TELEGRAM BOT TOKEN")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"

    try:
        response = requests.get(url, timeout=10)

        print(f"HTTP status: {response.status_code}")
        print(f"Response: {response.text}")

        return response.status_code == 200

    except Exception as e:
        print(f"Telegram connection error: {e}")
        return False
def trigger_snipe_view(request):

    """
    HTTP Trigger Endpoint: /api/trigger/
    Params: key (required), force (optional boolean to bypass match hours)
    """
    test_telegram_bot()
    key = request.GET.get("key")
    if key != CRON_SECRET:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    is_forced = request.GET.get("force", "").lower() == "true"
    if not is_active_window() and not is_forced:
        return JsonResponse({"status": "skipped", "reason": "Outside active match window"})

    results = []
    for username in TARGET_ACCOUNTS:
        tweet = fetch_latest_tweet(username)
        if tweet:
            # ID extraction supporting integer and string formats
            tweet_id = str(tweet.get("id") or tweet.get("id_str") or "")
            tweet_text = tweet.get("text") or tweet.get("full_text") or ""
            
            if tweet_id and not is_tweet_processed(tweet_id):
                ai_reply = generate_ai_banter(tweet_text)
                send_telegram_approval(username, tweet_text, ai_reply, tweet_id)
                mark_tweet_processed(tweet_id)
                results.append({"account": username, "status": "sniped", "tweet_id": tweet_id})
            elif tweet_id:
                results.append({"account": username, "status": "already_processed", "tweet_id": tweet_id})
            else:
                results.append({"account": username, "status": "missing_id_in_payload"})
        else:
            results.append({"account": username, "status": "no_tweet_found"})

    return JsonResponse({
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "results": results
    })

def health_check(request):
    """Public health endpoint: /api/health/"""
    return JsonResponse({"status": "healthy", "service": "Football Tweet Sniper API"})