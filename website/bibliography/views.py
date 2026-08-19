from django.shortcuts import render, get_object_or_404
from chem.models import Molecule
from refs.models import Source
from chem.utils import categorise_molecules

def bibliography_by_molecule(request):
    molecules = Molecule.objects.all()
    molecule_types = categorise_molecules(molecules)
    return render(request, 'bibliography/bibliography_by_molecule.html',
                  {'molecule_types': molecule_types})

def molecule_bibliography(request, molecule_slug, lineshapes):
    """Returns the bibliography for a Molecule identified by its slug."""

    molecule = get_object_or_404(Molecule, slug=molecule_slug)
    c = {'molecule': molecule}
    sources = (Source.objects.filter(tags__name=molecule.ordinary_formula)
                    .order_by('-year'))
    c['sources'] = sources
    lineshape_sources = (Source.objects.filter(tags__name=molecule.ordinary_formula)
                    .filter(tags__name='line shapes').order_by('-year'))
    c['lineshape_sources'] = lineshape_sources
    c['lineshapes'] = lineshapes
    if lineshapes:
        c['sources'] = lineshape_sources
    return render(request, 'bibliography/molecule_bibliography.html', c)
