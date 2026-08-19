import os
import sys
sys.path.append('/srv/www/exomol3')
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

import glob
from exomol3.settings import DATA_DIR

from data.models import DataSet

DB_URL_STEM = 'http://exomol.com/db'

if len(sys.argv) == 2:
    dataset_name = sys.argv[1]
    add_all_sizes = False
    if dataset_name == 'all':
        add_all_sizes = True
else:
    print('Usage is:')
    print('   {} all -- set file sizes for all DataSets'
                .format(sys.argv[0]))
    print('or {} <dataset name>'.format(sys.argv[0]))
    sys.exit(1)

if not add_all_sizes:
    # We're setting one particular DataSet's file sizes
    try:
        datasets = [DataSet.objects.get(name=dataset_name)]
    except DataSet.DoesNotExist:
        print('No such DataSet: {}'.format(dataset_name))
        sys.exit(1)
else:
    # Set all file sizes
    datasets = DataSet.objects.all()

links = set()
for dataset in datasets:
    data_collections = dataset.datacollection_set.filter(external=False)
    for data_collection in data_collections:
        links.update(data_collection.link.filter(local_file=True))

for link in links:
    filepath = link.url
    if not filepath.startswith('/db/'):
        print('Skipping unexpected filepath:', filepath)
        continue
    filepath = os.path.join(DATA_DIR, filepath.lstrip('/db/'))
    if not os.path.exists(filepath):
        print('Skipping missing filepath:', filepath)
        continue
    filesize = os.path.getsize(filepath)
    if link.size != filesize:
        print('Updating file size for', filepath, ':', filesize)
        link.size = filesize
        link.save()
