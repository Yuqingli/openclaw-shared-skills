"""
Discover new accounts to follow based on overlap from existing watchlist
"""
import json
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(__file__))

from x_following import get_following

DATA_DIR = r"C:\Users\yuqin\.openclaw\workspace\data"

def load_watchlist():
    with open(os.path.join(DATA_DIR, "x-watchlist.json")) as f:
        return json.load(f)

def discover_accounts(category=None, min_followed_by=5, min_followers=10000, limit=50):
    """Find accounts followed by multiple people in the watchlist"""
    watchlist = load_watchlist()
    
    # Get accounts in the specified category
    if category:
        seed_accounts = [a["username"] for a in watchlist["accounts"] if category in a.get("categories", [])]
    else:
        seed_accounts = [a["username"] for a in watchlist["accounts"]]
    
    existing_usernames = set(a["username"].lower() for a in watchlist["accounts"])
    
    print(f"Analyzing following lists for {len(seed_accounts)} accounts in '{category or 'all'}' category...")
    print(f"Looking for accounts followed by >= {min_followed_by} of them\n")
    
    # Collect all following
    all_following = {}
    
    for i, username in enumerate(seed_accounts, 1):
        print(f"[{i}/{len(seed_accounts)}] Fetching @{username}...", end=" ", flush=True)
        try:
            following = get_following(username, count=200)
            print(f"{len(following)} accounts")
            
            for f in following:
                uid = f["id"]
                if uid not in all_following:
                    all_following[uid] = {"info": f, "followed_by": set()}
                all_following[uid]["followed_by"].add(username)
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    # Filter and sort
    candidates = []
    for uid, data in all_following.items():
        username_lower = data["info"]["username"].lower()
        if username_lower in existing_usernames:
            continue  # Skip already tracked
        if len(data["followed_by"]) >= min_followed_by:
            if data["info"]["followers"] >= min_followers:
                candidates.append({
                    **data["info"],
                    "followed_by_count": len(data["followed_by"]),
                    "followed_by_list": list(data["followed_by"])
                })
    
    # Sort by followed_by_count desc, then followers desc
    candidates.sort(key=lambda x: (x["followed_by_count"], x["followers"]), reverse=True)
    
    return candidates[:limit]

if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "AI"
    min_followed = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    
    candidates = discover_accounts(category=category, min_followed_by=min_followed, limit=limit)
    
    print(f"\n{'='*70}")
    print(f"Found {len(candidates)} accounts followed by >= {min_followed} of your {category} list:\n")
    
    for i, user in enumerate(candidates, 1):
        desc = user['description'][:60].replace('\n', ' ') if user['description'] else ''
        verified = '✓' if user['verified'] else ''
        print(f"{i:2}. @{user['username']} {verified} — {user['followers']:,} followers")
        print(f"    Followed by {user['followed_by_count']}: {', '.join('@'+u for u in user['followed_by_list'][:5])}")
        if desc:
            print(f"    {desc}...")
        print()
