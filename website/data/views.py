import os
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.template import RequestContext
from django.db.models import Q
from chem.models import Molecule, Isotopologue
from chem.utils import categorise_molecules
from data.models import DataCollection, DataType, DataSet, Versioning
from django.conf import settings

broadening_type = DataType.objects.get(name='broadening coefficients')

def get_broadening_collection(molecule):
    """Get the first DataCollection of broadening coefficients for molecule."""

    broadening_collection = DataCollection.objects.filter(
            isotopologue__molecule=molecule, data_type=broadening_type).first()
    return broadening_collection


def get_spectrum_image_url(isotopologue_slug, dataset_name):
    spectrum_image = '{}__{}__spectrum.png'.format(isotopologue_slug,
            dataset_name)
    if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'uploads',
                            'spectrum-images', spectrum_image)):
        spectrum_image_url = os.path.join(settings.MEDIA_URL, 'uploads',
                                          'spectrum-images', spectrum_image)
        return spectrum_image_url
 
def search(request):
    c = {}
    if request.GET:
        ordinary_formula = request.GET.get('ordinary_formula')
        dataset_name = request.GET.get('dataset_name')
        c['molecules'] = Molecule.objects.filter(
                            ordinary_formula__exact=ordinary_formula)
        c['isotopologues'] = Isotopologue.objects.filter(
                            ordinary_formula__exact=ordinary_formula)
        c['datasets'] = DataSet.objects.filter(name__exact=dataset_name)
    return render(request, 'pages/data/search.html', c)
 
#####################################################################
# These view methods are for the navigation:
# molecule > isotopologue > dataset > [data files]
#####################################################################

def isotopologues(request, molecule_slug):
    """Renders the page of isotopologues for a specified molecule."""

    molecule = get_object_or_404(Molecule, slug=molecule_slug)
    isotopologues = Isotopologue.objects.filter(molecule=molecule)
    # Only report isotopologues that have data collections to show.
    isotopologues = [iso for iso in isotopologues
                        if iso.datacollection_set.all()]
    c = {'molecule': molecule, 'isotopologues': isotopologues}

    # Retrieve the broadening coefficient data sets for this molecule
    c['broadening_collection'] = get_broadening_collection(molecule)

    return render(request, 'pages/data/isotopologues.html', c)

def get_datasets_from_data_collections(data_collections):
    """Returns all the distinct data sets from data_collections.

    Given a QuerySet of DataCollection objects, returns the set of the
    distinct DataSet objects to which they belong.

    """

    return set(data_collection.data_set
                    for data_collection in data_collections)

def isotopologue_datasets(request, molecule_slug, isotopologue_slug):
    """Renders the page of datasets belonging to a given isotopologue."""

    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)
    data_collections = DataCollection.objects.filter(
                  isotopologue=isotopologue).exclude(
                    data_type__type_str='broadening_coefficients'
                  ).order_by("data_type")
    c = {'isotopologue': isotopologue, 'data_collections': data_collections}
    return render(request, 'pages/data/isotopologue_datasets.html', c)


def isotopologue_dataset_metadata(request, isotopologue, dataset, version):
    # XXX TODO
    json_path = os.path.join(settings.DATA_DIR, isotopologue.molecule.slug,
                isotopologue.slug, dataset.name)
    json_stem = f'{isotopologue.slug}__{dataset.name}'
    if version:
        json_stem += f'__{version}'
    json_name = os.path.join(json_path, json_stem + '.def.json')
    with open(json_name) as fi:
        dd = json.loads(fi.read())

    c = {'dd': dd}
    return render(request, 'pages/data/isotopologue_dataset_metadata.html', c)


def get_versioning_information(dataset, isotopologue, version):
    # Get the latest Versioning object.
    try:
        versioning = latest_versioning = Versioning.objects.filter(data_set=dataset,
                                         isotopologue=isotopologue).first()
    except Versioning.DoesNotExist:
        versioning = latest_versioning = None

    if latest_versioning and version:
        # Get the requested version.
        versioning = Versioning.objects.get(data_set=dataset,
                                isotopologue=isotopologue, version=version)
    
    is_latest_version = versioning == latest_versioning
    return {'versioning': versioning, 'is_latest_version': is_latest_version}


def metadata_export_response(request, export_format, isotopologue, dataset,
                    is_latest_version, version):
    export_format = export_format.lower()
    if export_format == 'json':
        # XXX TODO Versioning!
        return HttpResponseRedirect(f'/db/{isotopologue.molecule.slug}/'
                f'{isotopologue.slug}/{dataset.name}/'
                f'{isotopologue.slug}__{dataset.name}.json')
        # XXX TODO get rid of this!
        return JsonResponse(dataset.serialize(isotopologue))
    elif export_format == 'html':
        if is_latest_version:
            # The JSON filename does not include the version number if it
            # is for the most recent version.
            version = None
        return isotopologue_dataset_metadata(request, isotopologue,
                        dataset, version)
    elif export_format == 'def':
        return HttpResponseRedirect(f'/db/{isotopologue.molecule.slug}/'
                f'{isotopologue.slug}/{dataset.name}/'
                f'{isotopologue.slug}__{dataset.name}.def')
    raise Http404


def isotopologue_dataset_data(request, molecule_slug, isotopologue_slug,
                              dataset_name, version=None):
    """Renders the page of data corresponding to a given DataSet.

    Given a DataSet name, render a page of all the DataCollections in that
    DataSet. E.g. "All data collections from the BT2 data set for (1H)2(16O)".

    """

    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)
    dataset = get_object_or_404(DataSet, name=dataset_name)

    c = {'isotopologue': isotopologue, 'dataset': dataset}
    c.update(get_versioning_information(dataset, isotopologue, version))

    # Export metadata instead of rendering the data page.
    export_format = request.GET.get('export') 
    if export_format:
        return metadata_export_response(request, export_format, isotopologue,
                    dataset, c['is_latest_version'], version)

    data_collections = dataset.datacollection_set.filter(
                            isotopologue=isotopologue).exclude(
                            data_type__type_str='broadening_coefficients')

    # XXX For now, we have to allow that some DataCollection objects don't
    # have their version numbers attached.

    if c['versioning']:
        version = c['versioning'].version if c['versioning'] else None
    if c['is_latest_version']:
        # For the latest version, version number may or may not be present.
        query = Q(version=version) | Q(version=None)
        _data_collections = data_collections.filter(query)
    else:
        _data_collections = data_collections.filter(version=version)
    if _data_collections.count() == 0:
        _data_collections = data_collections
    data_collections = _data_collections

    c['data_collections'] = data_collections

    c['spectrum_image_url'] = get_spectrum_image_url(
                                    isotopologue_slug, dataset_name)

    return render(request, 'pages/data/isotopologue_dataset_data.html', c)


#####################################################################
# These view methods are for the navigation:
# data-type > molecule > isotopologue > dataset > [data files]
#####################################################################

def get_isotopologues_by_data_collection(data_collections):
    """Returns the distinct isotopologues from data_collections.

    Given a QuerySet of DataCollection objects, returns the set of distinct
    Isotopologue objecs featured amongst them.

    """

    return set(data_collection.isotopologue
                            for data_collection in data_collections)

def get_isotopologues_by_data_type(data_type):
    """Returns the distinct isotopologues with data of type data_type.

    Given a DataType name, returns the set of isotopologues with one
    or more DataCollection of that DataType. E.g. "all isotopologues with
    line lists".

    """

    data_collections = DataCollection.objects.filter(data_type=data_type)
    isotopologues = get_isotopologues_by_data_collection(data_collections)
    return isotopologues

def datatype_molecules(request, data_type):
    """Renders the page of molecules with data of data_type.

    Given a DataType name, renders the page listing molecules with any
    isotopologues which have data of that type in the database.

    """
    data_type = get_object_or_404(DataType, type_str=data_type)
    isotopologues = get_isotopologues_by_data_type(data_type)
    molecules = (Molecule.objects.filter(isotopologue__in=isotopologues).
                            distinct())

    molecule_types = categorise_molecules(molecules)

    c = {'data_type': data_type, 'molecule_types': molecule_types}
    return render(request, 'pages/data/datatype_molecules.html', c)

def datatype_isotopologues(request, data_type, molecule_slug):
    """Renders the page of isotopologues with data of data_type.

    Given a DataType name, renders the page listing isotopologues with any
    which have data of that type in the database.

    """

    molecule = get_object_or_404(Molecule, slug=molecule_slug)
    data_type = get_object_or_404(DataType, type_str=data_type)
    data_collections = ( DataCollection.objects.filter(data_type=data_type).
                filter(isotopologue__in=molecule.isotopologue_set.all()).
                exclude(data_type__type_str='broadening_coefficients') )
    isotopologues = get_isotopologues_by_data_collection(data_collections)
    c = {'molecule': molecule, 'data_type': data_type,
         'isotopologues': isotopologues}

    # Retrieve the broadening coefficient data sets for this molecule
    if data_type == broadening_type:
        c['broadening_collection'] = get_broadening_collection(molecule)

    return render(request, 'pages/data/datatype_isotopologues.html', c)

def datatype_isotopologue_datasets(request, data_type, molecule_slug,
                                isotopologue_slug):
    """Renders the page of datasets for a given isotopologue and data type.

    Given a DataType name and an Isotopologue slug, render the page listing
    all data sets belonging to the corresponding Isotopologue object and
    data type. E.g. "All datasets for (1H)2(16O) line lists".

    """

    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)
    data_type = get_object_or_404(DataType, type_str=data_type)
    data_collections = (DataCollection.objects.filter(
            isotopologue=isotopologue).filter(data_type=data_type))
    datasets = get_datasets_from_data_collections(data_collections)
    c = {'isotopologue': isotopologue, 'data_type': data_type,
         'datasets': datasets}
    return render(request, 'pages/data/datatype_isotopologue_datasets.html', c)

def datatype_isotopologue_dataset_data(request, data_type, molecule_slug,
                               isotopologue_slug, dataset_name, version=None): 
    """Renders the page of data for a given dataset and data type.

    Given a DataType name and DataSet name, render a page of all the
    DataCollections belonging to that DataSet corresponding to the DataType.
    E.g. "all line list DataCollections belonging to the BT2 DataSet for
    (1H)2(16O)".

    """

    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)
    data_type = get_object_or_404(DataType, type_str=data_type)
    dataset = get_object_or_404(DataSet, name=dataset_name)
    data_collections = dataset.datacollection_set.filter(
                                            isotopologue=isotopologue)

    c = {'isotopologue': isotopologue, 'data_type': data_type,
         'dataset': dataset}
    c.update(get_versioning_information(dataset, isotopologue, version))

    # Export metadata instead of rendering the data page.
    export_format = request.GET.get('export') 
    if export_format:
        return metadata_export_response(request, export_format, isotopologue,
                    dataset, c['is_latest_version'], version)

 
    if c['versioning']:
        version = c['versioning'].version if c['versioning'] else None
    if c['is_latest_version']:
        # For the latest version, version number may or may not be present.
        query = Q(version=version) | Q(version=None)
        _data_collections = data_collections.filter(query)
    else:
        _data_collections = data_collections.filter(version=version)
    if _data_collections.count() == 0:
        _data_collections = data_collections
    data_collections = _data_collections

    c['data_collections'] = data_collections

    if data_type.type_str == 'linelist':
        c['spectrum_image_url'] = get_spectrum_image_url(isotopologue_slug,
                                                         dataset_name)

    return render(request, 
                  'pages/data/datatype_isotopologue_dataset_data.html', c)
