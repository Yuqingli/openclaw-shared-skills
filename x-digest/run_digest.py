"""
Run X/Twitter digest - fetch tweets since last digest
"""
import json
import sys
import os
from datetime import datetime, timezone
from dateutil import parser as dateparser

# Import the fetch functions
sys.path.insert(0, os.path.dirname(__file__))
from x_fetch import get_user_tweets, load_watchlist, save_watchlist

def parse_twitter_date(date_str):
    """Parse Twitter's date format"""
    return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")

def format_time_ago(dt):
    """Format a datetime as time ago"""
    now = datetime.now(timezone.utc)
    diff = now - dt
    hours = diff.total_seconds() / 3600
    if hours < 1:
        return f"{int(diff.total_seconds()/60)}m ago"
    elif hours < 24:
        return f"{int(hours)}h ago"
    else:
        return f"{int(hours/24)}d ago"

def format_number(n):
    """Format large numbers with K/M suffix"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def log(msg):
    print(msg, flush=True)

def run_digest(since_str=None):
    watchlist = load_watchlist()
    
    # Parse since date
    if since_str:
        since = dateparser.parse(since_str)
    else:
        since = dateparser.parse(watchlist.get("lastDigest", "2026-02-01T00:00:00"))
    
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    
    log(f"Fetching tweets since: {since.isoformat()}")
    log(f"Accounts to check: {len(watchlist['accounts'])}\n")
    
    all_tweets = []
    errors = []
    
    for account in watchlist["accounts"]:
        username = account["username"]
        categories = account.get("categories", ["other"])
        
        try:
            tweets = get_user_tweets(username, count=15)
            new_tweets = []
            
            for t in tweets:
                tweet_time = parse_twitter_date(t["created_at"])
                if tweet_time > since:
                    t["username"] = username
                    t["categories"] = categories
                    t["parsed_time"] = tweet_time
                    new_tweets.append(t)
            
            if new_tweets:
                all_tweets.extend(new_tweets)
                print(f"✓ @{username}: {len(new_tweets)} new tweets")
            else:
                print(f"· @{username}: no new tweets")
                
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "403" in error_msg:
                errors.append(f"@{username}: Auth error (cookies may be expired)")
            else:
                errors.append(f"@{username}: {error_msg[:100]}")
            print(f"✗ @{username}: {error_msg[:50]}")
    
    # Group by category
    by_category = {}
    for t in all_tweets:
        for cat in t["categories"]:
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(t)
    
    # Sort each category by engagement (likes + retweets)
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x["likes"] + x["retweets"], reverse=True)
    
    # Format output
    print("\n" + "="*50)
    print(f"🐦 X Digest — {datetime.now().strftime('%b %d, %Y')}")
    print("="*50 + "\n")
    
    if not all_tweets:
        print("No new tweets since last digest.")
    else:
        for cat, tweets in sorted(by_category.items()):
            print(f"\n📁 {cat.upper()} ({len(tweets)} new)\n")
            
            # Show top 10 per category max
            for t in tweets[:10]:
                text = t['text'].replace('\n', ' ')
                if len(text) > 200:
                    text = text[:197] + "..."
                time_ago = format_time_ago(t["parsed_time"])
                
                print(f"• @{t['username']}: \"{text}\"")
                print(f"  ❤️ {format_number(t['likes'])}  🔁 {format_number(t['retweets'])}  — {time_ago}")
                print(f"  {t['url']}\n")
    
    if errors:
        print("\n⚠️ Errors:")
        for e in errors[:5]:
            print(f"  {e}")
    
    # Update last digest time
    watchlist["lastDigest"] = datetime.now(timezone.utc).isoformat()
    save_watchlist(watchlist)
    print(f"\n✅ Updated lastDigest to {watchlist['lastDigest']}")

if __name__ == "__main__":
    since = sys.argv[1] if len(sys.argv) > 1 else None
    run_digest(since)
