from django.contrib import admin
from news.models import News, UpdateAnnouncement

class NewsAdmin(admin.ModelAdmin):
    fields = [('date', 'important'), 'headline', 'content', ]

admin.site.register(News, NewsAdmin)

class UpdateAnnouncementAdmin(admin.ModelAdmin):
    fields = [('date',), 'headline', 'content', 'dataset']

admin.site.register(UpdateAnnouncement, UpdateAnnouncementAdmin)
