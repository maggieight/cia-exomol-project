from mezzanine.pages.page_processors import processor_for
from django.core.exceptions import PermissionDenied
from mezzanine.conf import settings
import requests

from news.models import News, UpdateAnnouncement

@processor_for('/')
def home(request, page):
    news_items = News.objects.all().order_by('-date')[:3]
    update_announcements = UpdateAnnouncement.objects.all().order_by(
                                                                '-date')[:3]

    return {'news_items': news_items,
            'update_announcements': update_announcements}

def validate_real_user(g_recaptcha_response):
    data = {
        'response': g_recaptcha_response,
        'secret': settings.RECAPTCHA_SECRET_KEY
    }
    response = requests.post('https://www.google.com/recaptcha/api/siteverify',
                             data=data)
    result_json = response.json()
    success = result_json.get('success')
    score = result_json.get('score')
    return success and score and score > 0.5 

@processor_for('contact')
def contact_form(request, page):
    """A simple spam detector."""

    
    # Visitors are requested to provide the answer to the sum 1 + 2 =
    # which hopefully bots often won't complete correctly.
    if request.POST:
        g_recaptcha_response = request.POST.get('g-recaptcha-response')
        is_real_user = validate_real_user(g_recaptcha_response)
        if not is_real_user:
            raise PermissionDenied
    return {'RECAPTCHA_SITE_KEY': settings.RECAPTCHA_SITE_KEY}
