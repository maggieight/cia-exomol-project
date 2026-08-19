from django.db import models
from django.db.models import Q
from taggit.managers import TaggableManager
from .bibtex_output import bibtex_output
from .source_utils import clean_authors, make_mandatory_tag, make_optional_tag
from .journal_abbrevs import journal_abbrevs

class SourceMethod(models.Model):
    method_name = models.CharField(max_length=32)
    def __str__(self):
        return self.method_name

    class Meta:
        db_table = 'source_method'
        app_label = 'refs'

class SourceType(models.Model):
    source_type = models.CharField(max_length=50)
    xsams_category = models.CharField(max_length=50)
    def __str__(self):
        return self.source_type

    class Meta:
        db_table = 'source_type'
        app_label = 'refs'

class Source(models.Model):
    # reference type (e.g. 'article', 'private communication')
    source_type = models.ForeignKey('SourceType', db_column='sourcetype_id',
                                    on_delete=models.CASCADE)
    # a list of the authors' names in a string as:
    # 'A.N. Other, B.-C. Person Jr., Ch. Someone-Someone, N.M.L. Haw Haw'
    authors = models.TextField(null=True, blank=True)
    # the article, book, or thesis title
    title = models.TextField(null=True, blank=True)
    # the title as HTML
    title_html = models.TextField(null=True, blank=True)
    # the title as LaTeX
    title_latex = models.TextField(null=True, blank=True)
    # the journal name
    journal = models.CharField(max_length=500, null=True, blank=True)
    # the volume (which may be a string)
    volume = models.CharField(max_length=10, null=True, blank=True)
    # the first page (which may be a string e.g. 'L123')
    page_start = models.CharField(max_length=10, null=True, blank=True)
    # the last page
    page_end = models.CharField(max_length=10, null=True, blank=True)
    # the year of publication, creation, or communication
    year = models.IntegerField(null=True, blank=True)
    # the institution name, if relevant and available
    institution = models.CharField(max_length=500, null=True, blank=True)
    # a note, perhaps containing cross-references of ref_id inside
    # square brackets
    note = models.TextField(null=True, blank=True)
    # the note as HTML
    note_html = models.TextField(null=True, blank=True)
    # the note as LaTeX
    note_latex = models.TextField(null=True, blank=True)
    # the Digital Object Identifier, if available
    doi = models.CharField(max_length=100, null=True, blank=True)
    # a URL to the source, if available
    url = models.TextField(null=True, blank=True)
    # the local filename, if available
    local_file = models.CharField(max_length=100, null=True, blank=True,
                                  db_column='local_file')
    # method: e.g. 'experimental', 'theory', 'extrapolation', 'guess'
    method = models.ForeignKey('SourceMethod', null=True, blank=True,
                               on_delete=models.CASCADE)
    # article number, used instead of page number for e.g. J.Chem.Phys. papers
    article_number = models.CharField(max_length=16, null=True, blank=True)
    # abstract
    abstract = models.TextField(null=True, blank=True)
    refID = models.CharField(max_length=100, null=True, blank=True,
                             db_column='refID')
    # source_list refers to a table giving the one-to-many relationship for a
    # Source note which cites (possibly more than one) sources
    #source_list = models.ManyToManyField('Source', symmetrical=False,
    #                                     null=True,
    #                                     blank=True)
    tags = TaggableManager()

    def __str__(self):
        if self.source_type.source_type == 'article':
            return '%d: %s, %s' % (self.id, self.authors, self.title)
        elif self.source_type.source_type in ('note', 'private communication'):
            return '%d: %s, %s' % (self.id, self.authors, self.note)
        elif self.source_type.source_type == 'database':
            return '%d: %s' % (self.id, self.note)
        else:
            return '%d: %s, %s' % (self.id, self.authors, self.title)

    class Meta:
        db_table = 'source'
        app_label = 'refs'

    def bibtex(self, *args, **kwargs):
        return bibtex_output(self, *args, **kwargs)

    def shorten_authors(self, nmax=5, nret=1):
        """
        Shorten the list of authors to nret names plus "et al." if there
        are more than nmax authors associated with a Source object.

        """

        authors = self.authors.split(',')
        if len(authors) > nmax:
            self.authors = ', '.join(authors[:nret]) + ' et al.'

    def html_article(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        if self.title_html:
            s_title = '"%s"' %  self.title_html
        elif self.title:
            s_title = '"%s"' %  self.title
        else:
            s_title = ''
        s_journal = self.journal
        if not s_journal:
            s_journal = 'unknown journal'
        if self.volume:
            s_volume = ' <b>%s</b>' % self.volume
        else:
            s_volume = ''

        if self.page_start:
            if self.page_end:
                s_pages = ', %s-%s' % (self.page_start, self.page_end)
            else:
                s_pages = ', {}'.format(self.page_start)
        else:
            s_pages = ''

        s_year = ''
        if self.year:
            s_year = ' (%s)' % (str(self.year))

        s_url = ''
        if self.url:
            s_url = self.url
        elif self.doi:
            if self.doi.startswith('http'):
                s_url = self.doi
            else:
                s_url = 'https://dx.doi.org/{}'.format(self.doi)
        if s_url:
            s_url = '<span class="noprint"> [<a href="%s">link to article'\
                    '</a>]</span>' % s_url

        s_refID = ''
        if self.refID:
            s_refID = '[%s]' % self.refID

        s = '%s, %s, <em>%s</em>%s%s%s.%s%s'\
                % (s_authors, s_title, s_journal, s_volume,
                   s_pages, s_year, s_url, s_refID)
        return s

    def xsams_article(self, NODEID):
        s_authors = clean_authors(self.authors)
        authors = [a.lstrip() for a in s_authors.split(',')]
        
        year = self.year
        xml = ['<Source sourceID="B%s-%d">' % (NODEID, self.id),
               '<Category>journal</Category>',
               make_optional_tag('SourceName', self.journal),
               make_mandatory_tag('Year', self.year),
              ]
        xml.append('<Authors>')
        for author in authors:
            xml.append('<Author><Name>%s</Name></Author>' % author)
        xml.append('</Authors>')
        xml.append(make_optional_tag('Title', self.title))
        xml.append(make_optional_tag('Volume', self.volume))
        xml.append(make_optional_tag('DigitalObjectIdentifier', self.doi))
        xml.append(make_optional_tag('ArticleNumber', self.article_number)),
        xml.append(make_optional_tag('PageBegin', self.page_start)),
        xml.append(make_optional_tag('PageEnd', self.page_end)),
        xml.append(make_optional_tag('UniformResourceIdentifier', self.url))
        xml.append('</Source>')
        return '\n'.join(xml)

    def html_note(self):
        return '%s.' % self.note_html

    def html_private_communication(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_institution = ''
        if self.institution:
            s_institution = ', %s' % self.institution
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s_pc = '%s%s%s, private communication%s.' % (s_authors,
                                        s_institution, s_note, s_year)
        return s_pc
        
    def html_proceedings(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        # for proceedings, the event details (e.g. conference venue and dates)
        # are stored in note and note_html
        s_event = ''
        if self.note_html:
            s_event = ', %s' % self.note_html
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s_url = ''
        if self.url:
            s_url = '<span class="noprint"> [<a href="%s">link to article'\
                    '</a>]</span>' % self.url
        s = '%s%s%s%s.%s' % (s_authors, s_title, s_event, s_year, s_url)
        return s

    def html_thesis(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_institution = self.institution
        if not s_institution:
            s_institution = '[unknown institution]'
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s = '%s%s%s, thesis, %s%s.' % (s_authors, s_title, s_note,
                                       s_institution, s_year)
        return s

    def html_database(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = ''
        s_title = ''
        if self.title_html:
            s_title = '"%s"' % self.title_html
        s_note = ''
        if self.note_html:
            s_note = '%s' % self.note_html
        s_url = ''
        if self.url:
            s_url = '<span class="noprint"><br/>url: <a href="%s">%s</a>'\
                    '</span>' % (self.url, self.url)
        s = ', '.join([x for x in [s_authors, s_title, s_note] if x])
        s = '%s, database.%s' % (s, s_url)
        return s

    def html_unpublished_data(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s = '%s%s%s, unpublished data%s.' % (s_authors, s_title, s_note,
                                             s_year)
        return s

    def html_report(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_institution = ''
        if self.institution:
            s_institution = ', %s' % self.institution
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s = '%s%s%s%s%s.' % (s_authors, s_title, s_note, s_institution, s_year)
        return s

    def html_in_preparation(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s = '%s%s%s%s, in preparation.' % (s_authors, s_title, s_note, s_year)
        return s

    def html_book(self):
        s_authors = self.authors
        if not s_authors:
            s_authors = 'unknown authors'
        s_title = ''
        if self.title_html:
            s_title = ', "%s"' % self.title_html
        elif self.title:
            s_title = ', "%s"' % self.title
        s_note = ''
        if self.note_html:
            s_note = ', %s' % self.note_html
        s_institution = ''
        if self.institution:
            s_institution = ', %s' % self.institution
        s_year = ''
        if self.year:
            s_year = ' (%d)' % self.year
        s = '%s%s%s%s%s.' % (s_authors,s_title, s_note, s_institution, s_year)
        return s

    # associate each source_type with a method for writing the source's HTML
    output_html = {'article': html_article,
                   'note': html_note,
                   'private_communication': html_private_communication,
                   'private communication': html_private_communication,
                   'proceedings': html_proceedings,
                   'thesis': html_thesis,
                   'database': html_database,
                   'unpublished_data': html_unpublished_data,
                   'unpublished data': html_unpublished_data,
                   'report': html_report,
                   'in preparation': html_in_preparation,
                   'book': html_book,
                   }

    def html(self, short_authors=False):
        """
        Call this method from the template to produce the HTML representation
        of a Source object.

        """
        return Source.output_html[self.source_type.source_type](self)

    output_xsams = {'article': xsams_article}

    def xsams(self, NODEID):
        try:
            return Source.output_xsams[self.source_type.source_type](self,
                                                                     NODEID)
        except KeyError:
            return '<!-- XSAMS output for %s is not supported -->'\
                             % self.source_type.source_type

    def serialize(self):
        d = {'qid': self.pk}
        d['cite'] = str(self)
        if self.doi:
            d['doi'] = self.doi
        if self.url:
            d['url'] = self.url
        if self.refID:
            d['refID'] = self.refID
        return d

def refs_search(term):
    try:
        doi_term = term
        if doi_term.startswith('doi:'):
            doi_term = term[4:]
            if not doi_term:
                return None
        query_result = Source.objects.get(doi=doi_term)
        return (query_result,)
    except Source.DoesNotExist:
        pass
    try:
        query_result = Source.objects.get(refID=term)
        return (query_result,)
    except Source.DoesNotExist:
        pass
    
    query_results = Source.objects.filter(Q(authors__icontains=term) |
                                          Q(title__icontains=term))
    return query_results

def parse_article_bibxml(entry_id, article_xml):

    warnings = []

    authors_xml = article_xml.getElementsByTagName('bibxml:author')
    authors = []
    for author_xml in authors_xml:
        author_name = author_xml.firstChild.nodeValue
        try:
            surname, initials = author_name.split(',')
            authors.append('%s %s' % (initials.strip(), surname))
        except ValueError:
            warnings.append('Missing author initials')
            authors.append(author_name)
    if not authors:
        warnings.append('Missing author(s)')
    authors = ', '.join(authors)

    journal_xml = article_xml.getElementsByTagName('bibxml:journal')
    if journal_xml.length == 1:
        journal = journal_xml[0].firstChild.nodeValue
        try:
            journal = journal_abbrevs[journal][1]
        except KeyError:
            warnings.append('Unidentified journal: %s' % journal)
            pass
    else:
        warnings.append('Missing journal')
        journal = 'Missing Journal' # XXX

    title_xml = article_xml.getElementsByTagName('bibxml:title')
    if title_xml.length == 1:
        title = title_xml[0].firstChild.nodeValue
    else:
        warnings.append('Missing title')
        title = 'Missing Title' # XXX

    year_xml = article_xml.getElementsByTagName('bibxml:year')
    if year_xml.length == 1:
        year = year_xml[0].firstChild.nodeValue
        try:
            year = int(year)
        except ValueError:
            warnings.append('Invalid year: %s' % year)
    else:
        warnings.append('Missing year')
        year = -1   # XXX

    volume_xml = article_xml.getElementsByTagName('bibxml:year')
    if volume_xml.length == 1:
        volume = volume_xml[0].firstChild.nodeValue
    else:
        warnings.append('Missing volume')
        volume = 'vXXX' # XXX

    pages_xml = article_xml.getElementsByTagName('bibxml:pages')
    if pages_xml.length == 1:
        pages = pages_xml[0].firstChild.nodeValue
        if '--' in pages:
            pages = pages.replace('--', '-')
        try:
            page_start, page_end = pages.split('-')
        except ValueError:
            page_start, page_end = pages, None
            warnings.append('Missing end page')
    else:
        warnings.append('Missing pages')

    doi_xml = article_xml.getElementsByTagName('bibxml:doi')
    if doi_xml.length == 1:
        doi = doi_xml[0].firstChild.nodeValue
    else:
        warnings.append('Missing doi')
        
    msg = '%s: %s, "%s", <em>%s</em> <b>%s</b>, %s-%s (%d)'\
           % (entry_id, authors, str(title), journal, volume, str(page_start),
              str(page_end), year)
    return msg, warnings

def add_ref_from_bibxml(entry_bibxml):
        entry_id = entry_bibxml.getAttribute('id')
        article_list = entry_bibxml.getElementsByTagName('bibxml:article')
        if not article_list:
            # TODO handle non-articles
            return entry_id, ['Entry is not an article']
        else:
            article_xml = article_list[0]
            msg, warnings = parse_article_bibxml(entry_id, article_xml)

        return msg, warnings
