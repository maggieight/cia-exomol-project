import os
import sys

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Isotopologue
from data.models import DataSet, Versioning

with open('Zenodo_doi_list.csv') as fi:
    fi.readline()
    for line in fi.readlines():
        fields = line.split(',')
        dataset_name = fields[0]
        iso_slug = fields[1]
        iso = Isotopologue.objects.get(slug=iso_slug)
        dataset = DataSet.objects.get(name=dataset_name)
        doi = fields[2]

        zenodo_doi, created = Versioning.objects.get_or_create(data_set=dataset,
                            isotopologue=iso, zenodo_doi=doi)
        print(dataset_name, iso_slug, doi, created)
