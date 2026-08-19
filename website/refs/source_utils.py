
def clean_authors(authors, default='unknown authors'):
    if not authors:
        return default
    return authors

# Some XML helper methods
def make_attrs_string(attrs):
    """
    Turn the dictionary of attributes, keyed as name: value into a string
    of XML attributes: 'name1="val1" name2="val2"...' etc.

    """

    return ' '.join(['%s="%s"' % x for x in attrs.items()])

def make_mandatory_tag(tag_name, contents, default='MISSING MANDATORY CONTENT',
                       attrs={}):
    """
    Make and return a mandatory tag (element) for the XML document, falling
    back to default if contents is None.

    """

    if contents is None:
        contents = default
    s_attrs = make_attrs_string(attrs)
    return '<%s %s>%s</%s>' % (tag_name, s_attrs, contents, tag_name)

def make_optional_tag(tag_name, contents, attrs={}):
    """
    Make and return an optional tag (element) for the XML document if
    contents is not None; otherwise return an empty string.

    """

    if contents is None:
        return ''
    s_attrs = make_attrs_string(attrs)
    return '<%s %s>%s</%s>' % (tag_name, s_attrs, contents, tag_name)
