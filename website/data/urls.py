from django.urls import path, re_path
from django.views.generic import TemplateView
import data.views

app_name='data'
urlpatterns = [

    path('search/', data.views.search),

    #####################################################################
    # These patterns are for the navigation:
    # molecule > isotopologue > dataset > [data files]
    #####################################################################
    # e.g. /data/molecules/H2O/1H2-16O/BT2/
    re_path(r'^molecules/(?P<molecule_slug>[-\w\d]+)/(?P<isotopologue_slug>[-\w\d]+)'
        r'/(?P<dataset_name>[-\w\d]+)/(?P<version>\d+)?$',
                        data.views.isotopologue_dataset_data, name='dataset'),
    # e.g. /data/molecules/H2O/1H2-16O/
    re_path(r'^molecules/(?P<molecule_slug>[-\w\d]+)/(?P<isotopologue_slug>[-\w\d]+)/$',
                        data.views.isotopologue_datasets, name='isotopologue'),
    # e.g. /data/molecules/H2O/
    re_path(r'^molecules/(?P<molecule_slug>[-\w\d]+)/$',
                                data.views.isotopologues, name='molecule'),


    #####################################################################
    # These patterns are for the navigation:
    # data-type > molecule > isotopologue > dataset > [data files]
    #####################################################################
    # e.g. /data/data-types/linelist/H2O/1H2-16O/BT2/
    re_path(r'^data-types/(?P<data_type>\w+)/(?P<molecule_slug>[-\w\d]+)/'
            r'(?P<isotopologue_slug>[-\w\d]+)/(?P<dataset_name>[-\w\d]+)/'
            r'(?P<version>\d+)?$$',
                              data.views.datatype_isotopologue_dataset_data),
    # e.g. /data/data-types/linelist/H2O/1H2-16O/
    re_path(r'^data-types/(?P<data_type>\w+)/(?P<molecule_slug>[-\w\d]+)/'
                 '(?P<isotopologue_slug>[-\w\d]+)/$',
                                data.views.datatype_isotopologue_datasets),
    # e.g. /data/data-types/linelist/H2O/
    re_path(r'^data-types/(?P<data_type>\w+)/(?P<molecule_slug>[-\w\d]+)/$',
                                data.views.datatype_isotopologues),
    # e.g. /data/data-types/linelist/
    re_path(r'^data-types/(?P<data_type>\w+)/$', data.views.datatype_molecules),
]
