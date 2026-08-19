from mezzanine.pages.page_processors import processor_for

from .models import DataCollection, DataType
from chem.models import Molecule, Isotopologue
from chem.utils import categorise_molecules

@processor_for('data/molecules')
def data_by_molecule(request, page):
    isotopologues = (DataCollection.objects.values_list('isotopologue').
                        distinct())
    isotopologues = Isotopologue.objects.filter(pk__in=isotopologues)
    molecule_pks = set(isotopologue.molecule.pk
            for isotopologue in isotopologues)

    molecules = Molecule.objects.filter(pk__in=molecule_pks)

    molecule_types = categorise_molecules(molecules)
    # Remove the atoms.
    molecule_types.pop('atoms', None)

    return {'molecule_types': molecule_types}


@processor_for('data/atoms')
def data_by_atom(request, page):
    isotopologues = (DataCollection.objects.values_list('isotopologue').
                        distinct())
    isotopologues = Isotopologue.objects.filter(pk__in=isotopologues)
    molecule_pks = set(isotopologue.molecule.pk
            for isotopologue in isotopologues)

    molecules = Molecule.objects.filter(pk__in=molecule_pks)

    molecule_types = categorise_molecules(molecules)
    # Retain only the atoms.
    molecule_types = {'atoms': molecule_types.pop('atoms', None)}

    return {'molecule_types': molecule_types}

@processor_for('data/data-types')
def data_by_type(request, page):
    data_types = DataType.objects.all()
    return {'data_types': data_types}

