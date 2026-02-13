"""
Twitter/X API client using session cookies
"""
import json
import requests
import sys
import io

# Fix Windows encoding for emoji
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os

DATA_DIR = r"C:\Users\yuqin\.openclaw\workspace\data"

def load_credentials():
    with open(os.path.join(DATA_DIR, "x-credentials.json")) as f:
        return json.load(f)

def load_watchlist():
    with open(os.path.join(DATA_DIR, "x-watchlist.json")) as f:
        return json.load(f)

def save_watchlist(data):
    with open(os.path.join(DATA_DIR, "x-watchlist.json"), "w") as f:
        json.dump(data, f, indent=2)

def get_session():
    creds = load_credentials()
    
    cookies = {
        "auth_token": creds["auth_token"],
        "ct0": creds["ct0"]
    }
    
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": creds["ct0"],
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    return cookies, headers

def get_user_id(username):
    cookies, headers = get_session()
    
    url = "https://x.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
    params = {
        "variables": json.dumps({"screen_name": username, "withSafetyModeUserFields": True}),
        "features": json.dumps({
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "responsive_web_twitter_article_notes_tab_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True
        }),
        "fieldToggles": json.dumps({"withAuxiliaryUserLabels": False})
    }
    
    resp = requests.get(url, params=params, cookies=cookies, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Error {resp.status_code}: {resp.text[:300]}")
    
    data = resp.json()
    return data["data"]["user"]["result"]["rest_id"]

def get_user_tweets(username, count=10):
    cookies, headers = get_session()
    user_id = get_user_id(username)
    
    url = "https://x.com/i/api/graphql/V7H0Ap3_Hh2FyS75OCDO3Q/UserTweets"
    
    features = {
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "articles_preview_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "creator_subscriptions_quote_tweet_preview_enabled": True
    }
    
    params = {
        "variables": json.dumps({
            "userId": user_id,
            "count": count,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": True,
            "withV2Timeline": True
        }),
        "features": json.dumps(features),
        "fieldToggles": json.dumps({"withArticlePlainText": False})
    }
    
    resp = requests.get(url, params=params, cookies=cookies, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Error {resp.status_code}: {resp.text[:500]}")
    
    data = resp.json()
    
    tweets = []
    try:
        instructions = data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                for entry in inst.get("entries", []):
                    if "tweet" in entry.get("entryId", ""):
                        try:
                            tweet_result = entry["content"]["itemContent"]["tweet_results"]["result"]
                            # Handle tweets with "tweet" wrapper (for retweets etc)
                            if "tweet" in tweet_result:
                                tweet_result = tweet_result["tweet"]
                            if "legacy" in tweet_result:
                                legacy = tweet_result["legacy"]
                                tweets.append({
                                    "id": legacy["id_str"],
                                    "text": legacy["full_text"],
                                    "created_at": legacy["created_at"],
                                    "retweets": legacy["retweet_count"],
                                    "likes": legacy["favorite_count"],
                                    "url": f"https://x.com/{username}/status/{legacy['id_str']}"
                                })
                        except (KeyError, TypeError):
                            continue
    except KeyError as e:
        raise Exception(f"Error parsing: {e}")
    
    return tweets

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "elonmusk"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    try:
        tweets = get_user_tweets(username, count=count)
        print(f"\nLatest {len(tweets)} tweets from @{username}:\n")
        for t in tweets:
            text = t['text'].replace('\n', ' ')[:150]
            print(f"[{t['created_at']}]")
            print(f"  {text}...")
            print(f"  ❤️ {t['likes']:,}  🔁 {t['retweets']:,}")
            print(f"  {t['url']}\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
