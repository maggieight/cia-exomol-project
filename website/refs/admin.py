from django.contrib import admin
from refs.models import Source

class SourceAdmin(admin.ModelAdmin):
    list_display = ('id', '__str__')
    ordering = ['id',]
    search_fields = ['authors', 'title']
admin.site.register(Source, SourceAdmin)

