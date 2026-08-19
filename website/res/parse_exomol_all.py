<<<<<<< HEAD
import os
import sys
sys.path.append('/Users/christian/www/exomol3')
sys.path.append('/srv/www/exomol3')
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Molecule
=======
>>>>>>> exomol-django2

def get_int(line):
    return int(line.split()[0])

def get_str(line):
    return line.split('#')[0].strip()

molec_names = {}
with open('exomol.all') as fi:
    assert fi.readline().lower().split()[0] == 'exomol.master'
    all_id = get_int(fi.readline())
    nmolec = get_int(fi.readline())
    for n in range(nmolec):
        nmolec_names = get_int(fi.readline())
        names = []
        for i in range(nmolec_names):
            names.append(get_str(fi.readline()))
        molec_formula = get_str(fi.readline())
        molec_names[molec_formula] = names
        niso = get_int(fi.readline())
        for j in range(niso):
            fi.readline()
            fi.readline()
            fi.readline()
            fi.readline()
            fi.readline()

for molec_formula, molec_names in molec_names.items():
<<<<<<< HEAD
    molecule = Molecule.objects.get(slug=molec_formula)
    names = '; '.join(molec_names)
    print(molecule, names)
    molecule.names = names
    molecule.save()
=======
    print(molec_formula, molec_names)
>>>>>>> exomol-django2
