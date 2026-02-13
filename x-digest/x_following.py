"""
Fetch following lists from Twitter/X
"""
import json
import requests
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = r"C:\Users\yuqin\.openclaw\workspace\data"

def load_credentials():
    with open(os.path.join(DATA_DIR, "x-credentials.json")) as f:
        return json.load(f)

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
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
    data = resp.json()
    return data["data"]["user"]["result"]["rest_id"]

def get_following(username, count=200):
    """Get list of accounts a user follows"""
    cookies, headers = get_session()
    user_id = get_user_id(username)
    print(f"Fetching following for @{username} (ID: {user_id})...")
    
    url = "https://x.com/i/api/graphql/eWTmcJY3EMh-dxIR7CYTKw/Following"
    
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
            "includePromotedContent": False
        }),
        "features": json.dumps(features)
    }
    
    resp = requests.get(url, params=params, cookies=cookies, headers=headers)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text[:500])
        return []
    
    data = resp.json()
    following = []
    
    try:
        instructions = data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                for entry in inst.get("entries", []):
                    if "user" in entry.get("entryId", ""):
                        try:
                            user_result = entry["content"]["itemContent"]["user_results"]["result"]
                            legacy = user_result.get("legacy", {})
                            following.append({
                                "id": user_result.get("rest_id"),
                                "username": legacy.get("screen_name"),
                                "name": legacy.get("name"),
                                "description": legacy.get("description", ""),
                                "followers": legacy.get("followers_count", 0),
                                "verified": user_result.get("is_blue_verified", False)
                            })
                        except (KeyError, TypeError):
                            continue
    except KeyError as e:
        print(f"Parse error: {e}")
    
    return following

def find_common_following(users, min_followers=1000):
    """Find accounts followed by all specified users"""
    all_following = {}
    
    for username in users:
        following = get_following(username)
        print(f"  @{username} follows {len(following)} accounts")
        for f in following:
            uid = f["id"]
            if uid not in all_following:
                all_following[uid] = {"info": f, "followed_by": []}
            all_following[uid]["followed_by"].append(username)
    
    # Find common (followed by all)
    common = []
    for uid, data in all_following.items():
        if len(data["followed_by"]) == len(users):
            if data["info"]["followers"] >= min_followers:
                common.append(data["info"])
    
    # Sort by followers
    common.sort(key=lambda x: x["followers"], reverse=True)
    return common

if __name__ == "__main__":
    users = sys.argv[1:] if len(sys.argv) > 1 else ["bcherny", "karpathy"]
    print(f"Finding common following for: {', '.join('@'+u for u in users)}\n")
    
    common = find_common_following(users, min_followers=5000)
    
    print(f"\n{'='*60}")
    print(f"Found {len(common)} accounts followed by all {len(users)} users:\n")
    
    for i, user in enumerate(common[:50], 1):
        desc = user['description'][:80].replace('\n', ' ') if user['description'] else ''
        verified = '✓' if user['verified'] else ''
        print(f"{i:2}. @{user['username']} {verified}")
        print(f"    {user['name']} — {user['followers']:,} followers")
        if desc:
            print(f"    {desc}...")
        print()
