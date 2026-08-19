# bibtex_output.py
from .latex_escape import latex_escape

entries = {'article': 'article',
           'note': 'misc',
           'book': 'book',
           'proceedings': 'inproceedings',
           'private communication': 'misc',
           'thesis': 'phdthesis',
           'database': 'misc',
           'unpublished data': 'unpublished',
           'report': 'techreport',
           'in preparation': 'misc'
          }

fields = {'article': ['author', 'title', 'journal', 'year', 'volume',
                       'pages', 'eid', 'doi'],  # XXX url
           'misc': ['author', 'title', 'note', 'year', 'url'],
           'book': ['author', 'title', 'year'], # XXX publisher
           'inproceedings': ['author', 'title', 'year'],    # XXX booktitle?
           'phdthesis': ['author', 'title', 'school', 'year'],
           'unpublished': ['author', 'title', 'note'],
           'techreport': ['author', 'title', 'institution', 'year'],
         }

def make_bibtex_author(source):
    try:
        s_authors = source.authors
        s_authors = latex_escape(s_authors)
        author_list = s_authors.split(',')
    except AttributeError:
        if source.source_type.source_type in ('note', 'database'):
            # authors not mandatory for note, database
            return ''
        return 'author = {unknown authors},\n',
    s_authors = ' AND '.join(author_list)
    if s_authors:
        return 'author = {%s},\n' % s_authors
    return ''

def make_bibtex_title(source):
    if source.title is None:
        return ''
    return 'title = {%s},\n' % source.title_latex 

def make_bibtex_year(source):
    if source.year is None:
        if source.source_type.source_type in ('note', 'database'):
            # don't worry about missing year for notes or databases
            return ''
        return 'year = {unknown year},\n'
    return 'year = {%d},\n' % source.year
    
def make_bibtex_journal(source):
    if source.journal is None:
        return 'journal = {unknown journal},\n'
    return 'journal = {%s},\n' % source.journal

def make_bibtex_volume(source):
    if source.volume is None:
        return 'volume = {unknown volume},\n'
    return 'volume = {%s},\n' % source.volume

def make_bibtex_pages(source):
    pages = ''
    if source.page_start:
        pages = source.page_start
    if source.page_end:
        pages = '%s-%s' % (pages, source.page_end)
    if pages:
         return 'pages = {%s},\n' % pages
    return ''
    
def make_bibtex_note(source):
    s_note = source.note_latex
    if s_note is None:
        s_note = ''
    if source.source_type.source_type == 'private communication':
        if s_note:
            s_note = 'Private communication: %s' % s_note
        else:
            s_note = 'Private communication'
    if not s_note:
        return ''
    return 'note = {%s},\n' % s_note

def make_bibtex_school(source):
    if source.institution is None:
        return ''
    return 'school = {%s},\n' % source.institution

def make_bibtex_institution(source):
    if source.institution is None:
        return ''
    institution = latex_escape(source.institution)
    return 'institution = {%s},\n' % institution

def make_bibtex_doi(source):
    if not source.doi:
        return ''
    return 'doi = {%s},\n' % source.doi

def make_bibtex_url(source):
    if not source.url:
        return ''
    return 'url = {%s},\n' % source.url

def make_bibtex_eid(source):
    if not source.article_number:
        return ''
    return 'eid = {%s},\n' % source.article_number

bibtex_field_makers = {'author': make_bibtex_author,
                       'title': make_bibtex_title,
                       'journal': make_bibtex_journal,
                       'year': make_bibtex_year,
                       'volume': make_bibtex_volume,
                       'pages': make_bibtex_pages,
                       'note': make_bibtex_note,
                       'school': make_bibtex_school,
                       'institution': make_bibtex_institution,
                       'doi': make_bibtex_doi,
                       'url': make_bibtex_url,
                       'eid': make_bibtex_eid,
                      }

def bibtex_output(source, prefix=''):
    entry = entries[source.source_type.source_type]
    bib_bits = ['@%s{%s-%d,\n' % (entry, prefix, source.id)]
    for field in fields[entry]:
        bib_bits.append(bibtex_field_makers[field](source))
    bib_bits.append('}\n')
    return ''.join(bib_bits)


