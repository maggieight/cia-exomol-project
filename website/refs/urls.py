from django.urls import include, path, re_path
from django.views.generic import TemplateView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = [
    path('save', 'refs.views.source_list_save'),
    path('upload', 'refs.views.upload_ref'),
    re_path('^(?P<molecule_slug>\w+)$',
                                'refs.views.molecule_bibliography_from_slug'),
    path('', 'refs.views.bibliography', name='bibliography'),
]
