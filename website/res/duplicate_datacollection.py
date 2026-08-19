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
from data.models import DataType, DataSet, DataCollection, Versioning

dc_id = sys.argv[1]

dc = DataCollection.objects.get(pk=dc_id)
print(dc.isotopologue, dc.data_set, dc.data_type, dc.version)

if not dc.version:
    sys.exit('Cannot duplicate a DataCollection without a version number.')
if dc.external:
    sys.exit('Cannot duplicate a DataCollection for an external resource.')

new_dc, created = DataCollection.objects.get_or_create(isotopologue=dc.isotopologue,
            data_type=dc.data_type, data_set=dc.data_set, external=dc.external,
            version=None)

if not created:
    sys.exit('I failed to duplicate this DataCollection because another without'
             ' a version number explicitly given already exists.')

new_dc.link.add(*dc.link.all())
new_dc.source.add(*dc.source.all())

print(f'The new DataCollection has ID {new_dc.id} and no explicit version number.'
      f' It will be treated as the new "latest" version.')
