from mezzanine.pages.page_processors import processor_for
from news.models import News, UpdateAnnouncement

NEWS_ITEMS_SHOWN = 5

@processor_for('activities/news')
def news_index(request, page):
    # Get the most NEWS_ITEMS_SHOWN most recent News items
    recent_news_items = News.objects.all().order_by('-date')[:NEWS_ITEMS_SHOWN]
    # Get the important News items (which don't expire)
    important_news_items = News.objects.filter(important=True)
    # Return a list of all News items to show, sorted in reverse
    # chronological order
    news_items = set(list(recent_news_items) + list(important_news_items))
    news_items = sorted(news_items, key=lambda e: e.date, reverse=True)
    return {'news_items': news_items}

@processor_for('activities/older-news')
def older_news(request, page):
    older_news_items = News.objects.all().order_by('-date')[NEWS_ITEMS_SHOWN:]
    return {'news_items': older_news_items}


@processor_for('activities/exomol-updates')
def exomol_updates(request, page):
    update_announcements = UpdateAnnouncement.objects.all().order_by(
                                                                '-date')[:3]
    return {'update_announcements': update_announcements}
