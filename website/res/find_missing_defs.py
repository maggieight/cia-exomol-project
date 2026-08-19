import os
import sys
sys.path.append('/srv/www/exomol3')
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from data.models import DataSet
from data.models import DataCollection

def_filenames = open('present_defs.txt').readlines()
present_defs = set()
for def_filename in def_filenames:
    bits = def_filename.split('/')
    iso, ds_name = bits[5], bits[6]
    present_defs.add((iso, ds_name))
for e in present_defs:
    print('-', e[0], '\t', e[1])

print('Number of present def files =', len(present_defs))

dcs = DataCollection.objects.filter(data_type_id=2)
print('Number of line list DataCollections found =', dcs.count())

dcs = set([(dc.isotopologue.slug, dc.data_set.name)
                    for dc in dcs if not dc.external])

missing_defs = dcs - present_defs
for e in missing_defs:
    print(e[0],'\t\t', e[1])
print(len(missing_defs))

#with open("missing_defs.txt", 'w') as fo:
#    for e in dcs:
#        if e not in sms:
#            print(e[0].ordinary_formula, e[1].name, file=fo)
