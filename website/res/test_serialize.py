import os
import sys
import json

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Isotopologue
from data.models import DataCollection, DataSet

ds = DataSet.objects.get(name='AlHambra')
iso = Isotopologue.objects.get(slug='26Al-1H')

s_json = json.loads(ds.json(iso))
print(json.dumps(s_json, indent=4))
#print(ds.json(iso))
