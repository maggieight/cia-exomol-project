from django.urls import path

from . import views

app_name = "cia"

urlpatterns = [
    path("", views.index, name="index"),
    path("species/<slug:species_slug>/", views.species, name="species"),
    path(
        "pairs-without-unique-active-species/",
        views.pairs_without_unique_active_species,
        name="pairs_without_unique_active_species",
    ),
    path("pairs/<slug:pair_slug>/", views.pair, name="pair"),
    path(
        "pairs/<slug:pair_slug>/datasets/<slug:dataset_id>/",
        views.dataset,
        name="dataset",
    ),
    path(
        "pairs/<slug:pair_slug>/datasets/<slug:dataset_id>/files/<path:filename>",
        views.download,
        name="download",
    ),
]
