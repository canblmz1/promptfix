# trend_scraper.py - FREE TREND FETCHER
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def get_hackernews_trends():
    """Hacker News frontpage'den AI/tech başlıklarını çek"""
    url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    top_ids = requests.get(url).json()[:10]
    
    stories = []
    for story_id in top_ids:
        story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()
        if story and 'title' in story:
            stories.append({
                'source': 'HackerNews',
                'title': story['title'],
                'url': story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                'score': story.get('score', 0)
            })
    return stories

def get_reddit_trends(subreddit="technology", limit=10):
    """Reddit'ten hot postları çek. User-Agent şart!"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    
    try:
        resp = requests.get(url, headers=headers).json()
        posts = []
        for post in resp['data']['children']:
            p = post['data']
            posts.append({
                'source': f'Reddit r/{subreddit}',
                'title': p['title'],
                'url': f"https://reddit.com{p['permalink']}",
                'score': p['score']
            })
        return posts
    except:
        return []

def get_google_trends_today():
    """Google Trends daily trends (RSS feed)"""
    # Not: Bu endpoint değişebilir, alternatif: pytrends kütüphanesi
    # Şimdilik basit bir mock / placeholder
    return []

def filter_ai_topics(stories):
    """AI/ML/Tech ile ilgili olanları filtrele"""
    keywords = ['ai', 'artificial intelligence', 'gpt', 'llm', 'openai', 'machine learning', 
                'chatgpt', 'claude', 'gemini', 'model', 'neural', 'automation', 'robot',
                'yapay zeka', 'chatbot', ' Generative']
    
    filtered = []
    for story in stories:
        title_lower = story['title'].lower()
        if any(k in title_lower for k in keywords):
            filtered.append(story)
    return filtered

def pick_best_topic(stories):
    """En yüksek skorlu veya en ilgi çekici konuyu seç"""
    if not stories:
        return "AI is changing everything you know about work"
    
    # Skora göre sırala, ilkini al
    best = sorted(stories, key=lambda x: x.get('score', 0), reverse=True)[0]
    return f"{best['title']} ({best['source']})"

# === MAIN ===
if __name__ == "__main__":
    print("🔍 Trendler çekiliyor...")
    
    hn = get_hackernews_trends()
    reddit = get_reddit_trends("technology")
    # reddit_ai = get_reddit_trends("artificial")  # Alternatif sub
    
    all_stories = hn + reddit
    ai_stories = filter_ai_topics(all_stories)
    
    print(f"\n📊 Bulunan toplam haber: {len(all_stories)}")
    print(f"🤖 AI/Tech ile ilgili: {len(ai_stories)}")
    
    if ai_stories:
        best = pick_best_topic(ai_stories)
        print(f"\n⭐ SEÇİLEN KONU: {best}")
        
        # Bu konuyu LLM'e göndermek için kaydet
        with open("today_topic.txt", "w", encoding="utf-8") as f:
            f.write(best)
        print("✅ today_topic.txt kaydedildi. LLM promptuna inject et.")
    else:
        print("⚠️ AI konusu bulunamadı, manuel konu girilmeli.")
