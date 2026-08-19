from django.shortcuts import render
from django.http import JsonResponse, Http404, HttpResponseBadRequest
from django.db.models import Q
from django.shortcuts import get_object_or_404

from chem.models import Molecule, Isotopologue
from data.models import DataType, DataCollection, Link

def query(request):
    molecule = request.GET.get('molecule')
    if molecule:
        q = Q(ordinary_formula=molecule) | Q(slug=molecule)
        molecule = get_object_or_404(Molecule, q)
    isotopologues = request.GET.get('isotopologues')
    if isotopologues:
        isotopologues = [s.strip() for s in isotopologues.split(',')]
        q = Q(ordinary_formula__in=isotopologues) | Q(slug__in=isotopologues)
        isotopologues = Isotopologue.objects.filter(q)
        if not isotopologues:
            raise Http404
    elif molecule:
        isotopologues = molecule.isotopologue_set.all()
    else:
        return HttpResponseBadRequest('Invalid query',
                                      content_type='text/plain')

    data_types = request.GET.get('datatype')
    if not data_types:
        data_types = 'linelist, energylevels, partitionfunction, opacity'
    data_types = [s.strip() for s in data_types.split(',')]
    data_types = DataType.objects.filter(type_str__in=data_types)

    query_response = {}
    for isotopologue in isotopologues:
        qi = query_response[isotopologue.ordinary_formula] = {
                'molecule': isotopologue.molecule.ordinary_formula,
                'mass /u': isotopologue.get_mass({'units': 'u'}),
        }
        for data_type in data_types:
            dc = qi[data_type.type_str] = {'data type': data_type.name}
            data_collections = DataCollection.objects.filter(
                            isotopologue=isotopologue,
                            data_type__type_str=data_type.type_str)
            for data_collection in data_collections:
                data_set = data_collection.data_set
                ds = dc[data_set.name] = {}
                ds['description'] = data_set.description
                ds['recommended'] = data_set.recommended
                files = ds['files'] = []
                for link in data_collection.link.all():
                    files.append(link.as_dict())
    return JsonResponse(query_response)
