
import os
import sys

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()
from django.conf import settings

from chem.models import Isotopologue
from data.models import DataSet, Versioning


def get_dataset_version(iso, ds, def_path):
    with open(def_path) as fi:
        for line in fi:
            line = line.strip()
            if line.endswith('Version number with format YYYYMMDD'):
                version = int(line[:50])
                return version
    print(f'No version number in {def_path}')
    return False
    

dss = DataSet.objects.all()
for ds in dss:
    iso_ids = ds.datacollection_set.all().values_list('isotopologue', flat=True)
    iso_ids = set(iso_ids)
    isos = Isotopologue.objects.filter(pk__in=iso_ids)
    for iso in isos:
        def_path = os.path.join(settings.DATA_DIR, iso.molecule.slug, iso.slug, ds.name)
        def_name = f'{iso.slug}__{ds.name}.def'
        def_path = os.path.join(def_path, def_name)
        if os.path.exists(def_path):
            print(iso, ds)
        else:
            print('Skipping:', iso, ds)
            continue

        version = get_dataset_version(iso, ds, def_path)
        print(version)
        if version:
            versioning, _ = Versioning.objects.get_or_create(data_set=ds, isotopologue=iso)
            versioning.version = version
            versioning.save() 
            
