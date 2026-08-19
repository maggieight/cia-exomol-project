import os
import sys
from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Isotopologue, Molecule

#molecules = Molecule.objects.all()
#for molecule in molecules:
#    print(f'{molecule.pk}, {molecule.ordinary_formula}, {molecule.tags.all()}')

isos = Isotopologue.objects.all()
for iso in isos:
    print(f'{iso.pk}, {iso.ordinary_formula}, {iso.molecule.ordinary_formula}')

