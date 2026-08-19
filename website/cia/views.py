from django.http import FileResponse, Http404
from django.shortcuts import render

from . import services


def _not_found(error):
    raise Http404(str(error))


def index(request):
    try:
        catalogue = services.list_catalogue()
    except services.CIADataError as error:
        _not_found(error)
    return render(request, "cia/index.html", catalogue)


def species(request, species_slug):
    try:
        species_data = services.get_species(species_slug)
    except services.CIADataError as error:
        _not_found(error)
    return render(request, "cia/species.html", {"species": species_data})


def pairs_without_unique_active_species(request):
    try:
        pairs = services.list_catalogue()["unassigned_pairs"]
    except services.CIADataError as error:
        _not_found(error)
    return render(
        request,
        "cia/pairs_without_unique_active_species.html",
        {"pairs": pairs},
    )


def pair(request, pair_slug):
    try:
        pair_data = services.get_pair(pair_slug)
    except services.CIADataError as error:
        _not_found(error)
    return render(request, "cia/pair.html", pair_data)


def dataset(request, pair_slug, dataset_id):
    try:
        dataset_data = services.get_dataset(pair_slug, dataset_id)
    except services.CIADataError as error:
        _not_found(error)
    return render(request, "cia/dataset.html", dataset_data)


def download(request, pair_slug, dataset_id, filename):
    try:
        path = services.downloadable_file(pair_slug, dataset_id, filename)
    except services.CIADataError as error:
        _not_found(error)
    content_type = (
        "application/json" if path.suffix.lower() == ".json" else "text/plain"
    )
    return FileResponse(
        path.open("rb"),
        as_attachment=False,
        filename=path.name,
        content_type=content_type,
    )
