from django.urls import re_path
import spectroscopic_model.views

urlpatterns = [
    re_path(r'(?P<molecule_slug>\w+)/(?P<isotopologue_slug>[-\w\d]+)'
        r'/(?P<dataset_name>[-\w\d]+)/$',
                                spectroscopic_model.views.specmodel_doc),
]
