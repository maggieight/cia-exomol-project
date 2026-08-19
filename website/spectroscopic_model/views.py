from django.shortcuts import render, get_object_or_404
from spectroscopic_model.models import SpectroscopicModel
from data.models import Isotopologue, DataSet

def specmodel_doc(request, molecule_slug, isotopologue_slug,
                              dataset_name):
    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)
    data_set = get_object_or_404(DataSet, name=dataset_name)
    try:
        specmodel = SpectroscopicModel.objects.get(isotopologue=isotopologue,
                        data_set=data_set)
        c = {'specmodel': specmodel}
        return render(request, 'spectroscopic_model/specmodel.html', c)
    except SpectroscopicModel.DoesNotExist:
        specmodel = None

    c = {'isotopologue': isotopologue, 'data_set': data_set}
    return render(request, 'spectroscopic_model/missing_model.html', c)
