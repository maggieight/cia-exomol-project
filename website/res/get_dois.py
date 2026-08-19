import os
import sys

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Isotopologue
from data.models import DataCollection, DataSet
from refs.models import Source

isos = Isotopologue.objects.all()

by_iso = True

if by_iso:
    # By Isotopolouge:
    for iso in isos:
        print(iso)
        iso_sources = set()
        for dc in DataCollection.objects.filter(isotopologue=iso):
            sources = dc.source.all()
            for source in sources:
                iso_sources.add(source)
        for source in iso_sources:
            print('    ', source.doi)
else:
    # By DataCollection
    for iso in isos:
        print(iso)
        for dc in DataCollection.objects.filter(isotopologue=iso):
            print('    ', dc.data_set, ':', dc.data_type)
            sources = dc.source.all()
            for source in sources:
                print('        ', source.doi)
