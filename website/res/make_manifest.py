import os
import sys
sys.path.append('/srv/www/exomol3')
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

import glob
from exomol3.settings import DATA_DIR
from chem.models import Isotopologue
from data.models import DataSet, DataCollection

DB_URL_STEM = 'http://exomol.com/db'

if len(sys.argv) == 3:
    iso_slug, data_set = sys.argv[1:]
    manifest_all = False
elif len(sys.argv) == 2 and sys.argv[1] == 'all':
    manifest_all = True
else:
    print('Usage is:')
    print('   {} all -- set manifest files for all DataSets'
                .format(sys.argv[0]))
    print('or {} <iso-slug> <dataset>'.format(sys.argv[0]))
    sys.exit(1)

if not manifest_all:
    # We're setting one particular manifest file
    try:
        isotopologue = Isotopologue.objects.get(slug=iso_slug)
    except Isotopologue.DoesNotExist:
        print('No such isotopologue: {}'.format(iso_slug))
        sys.exit(1)
    manifest_labels = [(isotopologue, data_set)]
else:
    # Set all manifest files
    data_collections = DataCollection.objects.filter(external=False)
    manifest_labels = set()
    for data_collection in data_collections:
        manifest_labels.add((data_collection.isotopologue,
                             data_collection.data_set.name))

def get_url_from_filename(filename):
    basename = os.path.basename(filename)
    url = '{}/{}'.format(url_stem, basename)
    return url

def write_url_to_manifest(filename, filesize=None):
    url = get_url_from_filename(filename)
    if filesize is None:
        filesize = os.path.getsize(filename)
    line = '{} {}'.format(url, filesize)
    print(line, file=fo)
    return len(line) + 1

for manifest_label in manifest_labels:
    isotopologue, data_set = manifest_label
    molec_slug = isotopologue.molecule.slug
    iso_slug = isotopologue.slug
    patt  = os.path.join(DATA_DIR, molec_slug, iso_slug, data_set, '*')
    files = glob.glob(patt)
    if not files:
        print('Failed to find files for {}/{}'.format(iso_slug, data_set))
        continue

    url_stem = '{}/{}/{}/{}'.format(DB_URL_STEM, molec_slug, iso_slug,
                                    data_set)
    manifest_file = os.path.join(DATA_DIR, molec_slug, iso_slug, data_set,
                                 '{}__{}.manifest'.format(iso_slug, data_set))
    manifest_file_size = 0
    with open(manifest_file, 'w') as fo:
        print('Writing manifest file: {}'.format(manifest_file))
        for filename in files:
            if filename.endswith('.manifest'):
                # Skip any existing manifest file, which we're over-writing
                continue
            manifest_file_size += write_url_to_manifest(filename)
        # Ignore edge-case of e.g. manifest file size being 999 bytes
        # We add 2: one for the space between URL and size and one for the CR
        manifest_file_size += (len(get_url_from_filename(manifest_file)) + 2
                           + len(str(manifest_file_size))
                              )
        write_url_to_manifest(manifest_file, manifest_file_size)
