import os
import sys
sys.path.append('/srv/www/exomol3')
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from data.models import DataSet
from data.models import DataCollection
from spectroscopic_model.models import SpectroscopicModel
        
dcs = DataCollection.objects.filter(data_type_id=2)
print('Number of line list DataCollections found =', dcs.count())

dcs = [(dc.isotopologue, dc.data_set) for dc in dcs if not dc.external]
sms = SpectroscopicModel.objects.all()
print('Number of SpectroscopicModels found =', sms.count())
sms = [(sm.isotopologue, sm.data_set) for sm in sms]

with open("missing_models.txt", 'w') as fo:
    for e in dcs:
        if e not in sms:
            print(e[0].ordinary_formula, e[1].name, file=fo)
