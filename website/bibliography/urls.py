from django.urls import path, re_path
import bibliography.views

app_name = 'bibliography'
urlpatterns = [
    re_path(r'^(?P<molecule_slug>\w+)/(?P<lineshapes>\w+)',
            bibliography.views.molecule_bibliography, {'lineshapes': True},
            name='molecule_bibliography'),
    re_path(r'^(?P<molecule_slug>\w+)',
            bibliography.views.molecule_bibliography, {'lineshapes': False},
            name='molecule_bibliography'),
    path('', bibliography.views.bibliography_by_molecule),
]
