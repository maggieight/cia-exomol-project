import logging
log = logging.getLogger('refs_logger')

escape = {
'Š': r'\v{S}',
'ł': r'\l',
'é': r'\'{e}',
'è': r'\`{e}',
'ë': r'\"{e}',
'ï': r'\"{i}',
'n̄': r'\={n}',
'ñ': r'\~{n}',
'ó': r'\'{o}',
'ò': r'\"{o}',
'ü': r'\"{u}',
'ö': r'\"{o}',

}

def latex_escape(s):
    """
    Replace non-ASCII characters with their escaped-versions, in so far as
    they can be identified from the dictionary escape.

    """

    uc = []
    for c in s:
        if ord(c) > 128:
            uc.append(c)
    for c in uc:
        try:
            s = s.replace(c, escape[c])
        except KeyError:
            log.warning('Warning! unescaped character, {}, in string:\n{}'
                                .format(c, s))
    return s

