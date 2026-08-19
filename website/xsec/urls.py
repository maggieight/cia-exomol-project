from django.urls import re_path
import xsec.views

urlpatterns = [
    re_path(r'^(?P<isotopologue_slug>[-\w\d]+)/$', xsec.views.isotopologue_xsec),
]
