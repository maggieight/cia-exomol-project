import os
import sys
from conf import exomol3_root

sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

import re
import argparse
from chem.models import Molecule
from refs.models import Source, SourceType
import codecs
import bibtexparser
from bibtexparser import bparser

# Make a dictionary of SourceType objects we recogise, keyed by name
source_types = ['article', 'book', 'proceedings']
source_types = SourceType.objects.filter(source_type__in=source_types)
source_types = dict([(st.source_type, st) for st in source_types])

# Map my BibTeX's entry types to my SourceType names
source_type_names = {'article': 'article',
                     'book': 'book',
                     #'inproceedings': 'proceedings',
                    }

# Build a mapping of abbreviations used within the Tennyson group for
# journal titles to their short but explicit forms

def build_dict(filename):
    ja = {}
    with open(filename) as fi:
        for line in fi.readlines():
            try:
                k, v = [e.strip() for e in line.split(' = ')]
            except ValueError:
                print('malformed line: ', line)
            ja[k] = v
    return ja

ja = {}
ja.update(build_dict('journal_abbrevs.txt'))
ja.update(build_dict('journal_abbrevs2.txt'))
ja.update(build_dict('journal_abbrevs3.txt'))

journal_titles = [line.strip() for line in
                        open('journal_titles.txt').readlines()]

parser = argparse.ArgumentParser(description='Upload references from .bib'
                ' format to the ExoMol(3) database.')
parser.add_argument('-u', dest='update', action='store_true', default=False,
                    help='actually update the database.')
parser.add_argument('-e', '--encoding', help='specify the character encoding'
                ' for the .bib file; default is cp1252', type=str)
parser.add_argument('bib_file', type=str, help='path to the .bib file to use')
parser.add_argument('ordinary_formula', type=str,
     help='"ordinary formula" for the molecule this bibliography belongs to.')
args = parser.parse_args()

out_header = '== Upload .bib file to database =='
print('='*len(out_header))
print(out_header)
print('='*len(out_header))
print('Update is {}'.format('ON' if args.update else 'OFF'))
if args.update:
    response = input('Please confirm you want to update the db? (y/N)')
    if response.lower() != 'y':
        print('Exiting. Bye.')
        sys.exit()

try:
    molecule = Molecule.objects.get(ordinary_formula=args.ordinary_formula)
except Molecule.DoesNotExist:
    print('Unrecognised molecule formula: {}'.format(args.ordinary_formula))
    sys.exit(1)

# First get the strings of journal abbreviations
journal_string_files = ['journals_astro.bib', 'journals_iso.bib', 'journals_phys.bib']
bibtex_strings = set()
for sf in journal_string_files:
    with open(sf) as fi:
        for line in fi:
            if line.startswith('@string'):
                js = line[8:line.index('=')].strip()
                # Duplicate the string definition because journal abbreviations
                # are resolved later using the journal_abbrevs<X>.txt files.
                bibtex_strings.add('@string{' + js + ' = {' + js + '}}')
bibtex_lines = list(bibtex_strings)

with codecs.open(args.bib_file, encoding=args.encoding, errors='ignore') as fi:
    bibtex_lines.extend(fi.readlines())

def ensure_first_lower(s):
    """Ensure that the first character of string s is lower case."""
    if not s:
        return ''
    return s[0].lower() + s[1:]

# A bit of pre-processing: ensure that the BibTeX keys (such as 'journal',
# 'author', etc. start with lower-case letters, not 'Journal' etc.)
for bibtex_line in bibtex_lines:
    bibtex_line = bibtex_line.lstrip()
    bibtex_line = ensure_first_lower(bibtex_line)

f_ja = open('journal_abbrevs3.txt', 'a')
f_jt = open('journal_titles.txt', 'a')

bparser_instance = bparser.BibTexParser(common_strings=True,
                                        #interpolate_strings=False,
                                        #ignore_nonstandard_types=True
                                       )
bib_database = bibtexparser.loads(''.join(bibtex_lines), parser=bparser_instance)
nadded = 0
for i, entry in enumerate(bib_database.entries):
    entry_type = entry['ENTRYTYPE']
    refID = entry['ID']

    try:
        source_type = source_types[source_type_names[entry_type]]
    except KeyError:
        # We don't recognise this BibTeX entry type, move along
        print('Skipping bib entry with type {}'.format(entry_type))
        continue

    # We have a citation we can do something with
    authors = entry['author']
    if authors:
        # Replace BibTeX-style "author1 AND author2 AND ..." with a
        # comma-separated string of author names.
        authors = ', '.join(re.split(' and | AND ', authors))

    title = entry.get('title')
    journal = entry.get('journal')
    if journal:
        try:
            journal = ja[journal]
        except KeyError:
            if journal not in journal_titles:
                # The journal field isn't a recognised abbreviation and it
                # isn't a recognised full journal title name.
                print('Warning: unrecognised journal abbreviation {}'
                      ' for entry {}'.format(journal, i))
                response = input('Is this a full journal title?')
                if response.lower() == 'y':
                    # It's a full journal title: update dict and text file
                    print(journal, file=f_jt)
                    f_jt.flush()
                    journal_titles.append(journal)
                else:
                    # It's an abbreviation: add it do the list
                    response = input('Add this journal abbreviation to the'
                                     ' list? (y/N)')
                    if response.lower() == 'y':
                        journal_title = input('Enter full journal title:')
                        print('{} = {}'.format(journal, journal_title),
                              file=f_ja)
                        ja[journal] = journal
                        if journal_title not in journal_titles:
                            print(journal_title, file=f_jt)
                            f_jt.flush()
                            journal_titles.append(journal_title)
                        print('Added {} = {}'.format(journal, journal_title))
                    else:
                        print('Skipping this entry')
                        continue
    elif entry_type == 'article':
        print('Skipping article: no journal field for entry {}:\n{}'
                                        .format(i, str(entry)))
        continue

    volume = entry.get('volume')
    
    article_number = entry.get('eid')
    pages = entry.get('pages', '')
    print('PAGES =', pages)
    pages = pages.replace('-', ' ').replace('–', ' ').split()
    if len(pages) == 2:
        page_start, page_end = pages
    elif len(pages) == 1:
        page_start, page_end = pages[0], None
        if page_start.startswith('0'):
            article_number = page_start
            page_start = None
    else:
        page_start, page_end = None, None

    year = entry.get('year')
    if year:
        year = int(year.strip('{}'))

    doi = entry.get('doi')
    url = entry.get('url') or entry.get('link')

    abstract = entry.get('abstract')

    publisher = entry.get('publisher', '')
    series = entry.get('series', '')
    isbn = entry.get('isbn', '')

    if journal:
        existing_sources = Source.objects.filter(journal=journal,
            volume=volume,page_start=page_start,page_end=page_end,year=year)
    elif source_type_names[entry_type] == 'book':
        existing_sources = Source.objects.filter(title=title,
            authors=authors,year=year)
    else:
        print('Error: no handler for source type {}'.format(
                                    source_type_names[entry_type]))
        continue
    if existing_sources.count():
        print('Skipping entry {} because it already occurs in the database'
              ' {} times:'.format(i, existing_sources.count()))
        for existing_source in existing_sources:
            print('--', existing_source)
            print('++', existing_source.tags.names())
            if molecule.ordinary_formula not in existing_source.tags.names():
                print('Adding tag!!!')
                if args.update:
                    existing_source.tags.add(molecule.ordinary_formula)
        continue
    
    nadded += 1
    if args.update:
        new_source = Source(source_type=source_type, authors=authors,
                    title=title, title_latex=title, journal=journal,
                    volume=volume, page_start=page_start, page_end=page_end,
                    year=year, doi=doi, url=url, article_number=article_number,
                    abstract=abstract, refID=refID)
        if source_type_names[entry_type] == 'book':
            new_source.note = 'Publisher: {}; Series = {}; isbn = {}'.format(
                                publisher, series, isbn)
        new_source.save()
        new_source.tags.add(molecule.ordinary_formula)
print('\nNumber of sources {}: {}'.format('added' if args.update else 'to add',
      nadded))
