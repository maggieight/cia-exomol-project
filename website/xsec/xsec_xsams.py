import os
from datetime import datetime

def xsams_xsec_chunk(NODEID, id, comment, sources, T, isotopologue,
                     numin, numax, dnu, sigma_name, sigma=[]):

    yield r"""<?xml version="1.0" encoding="UTF-8"?>
<XSAMSData xmlns="http://vamdc.org/xml/xsams/1.0"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns:cml="http://www.xml-cml.org/schema"
xsi:schemaLocation="http://vamdc.org/xml/xsams/1.0 http://vamdc.org/xml/xsams/1.0/xsams.xsd">"""

    yield '<Sources>'
    yield '    <Source sourceID="B%s-0">' % NODEID
    yield '        <Category>private communication</Category>'
    yield '        <Authors><Author><Name>C. Hill</Name></Author>'\
          '</Authors>'
    yield '        <Year>2013</Year>'
    yield '    </Source>'

    for source in sources:
        yield source.xsams(NODEID)

    yield '</Sources>'

    yield '<Environments>'
    yield '    <Environment envID="E%s-%d">' % (NODEID, id)
    yield '        <Temperature><Value units="K">%.1f</Value>'\
          '</Temperature>' % T
    yield '    </Environment>'
    yield '</Environments>'

    yield '<Species>'
    yield '    <Molecules>'
    #for xsams_iso_chunk in iso.xsams_iso_chunks(NODEID):
    #    yield xsams_iso_chunk
    yield isotopologue.xsams(NODEID)
    yield '    </Molecules>'
    yield '</Species>'

    yield '<Methods>\n    <Method methodID="MEXP">'
    yield '        <Category>theory</Category>'
    yield '        <Description>Calculated cross section from ExoMol'\
                  '</Description>'
    yield '    </Method>\n</Methods>'

    yield '<Processes>'
    yield '<Radiative>'
    yield '<AbsorptionCrossSection envRef="E%s-%d"'\
          ' id="P%s-XSC-1">' % (NODEID, id, NODEID)
    yield '    <Description>The absorption cross'\
          ' section for %s at %.1f K, calculated at'\
          ' %s. %s</Description>' % (isotopologue.ordinary_formula, T,
                    datetime.now().ctime(), comment)
    yield '    <X parameter="nu" units="1/cm">'
    n = int(round((numax - numin) / dnu)) + 1
    yield '        <LinearSequence count="%d" initial="%f"'\
                ' increment="%f"/>' % (n, numin, dnu)
    yield '    </X>'
    yield '    <Y parameter="sigma" units="cm2">'
    if sigma_name:
        # Reference to an external file containing the cross section
        yield '    <DataFile>%s</DataFile>' % os.path.basename(sigma_name)
    else:
        # The actual cross section data, inline with the XSAMS
        yield '    <DataList>%s</DataList>' % ' '.join([str(e) for e in sigma])
    yield '    </Y>'
    yield '    <Species>'
    yield '    <SpeciesRef>X%s-%s</SpeciesRef>' % (NODEID,
                                                   isotopologue.get_inchikey())
    yield '    </Species>'
    yield '</AbsorptionCrossSection>' 
    yield '</Radiative>'
    yield '</Processes>'

    yield '</XSAMSData>'

def write_xsams(NODEID, id, comment, sources, T, isotopologue, numin,
                numax, dnu, sigma_name, xsams_path):
    with open(xsams_path, 'w', encoding='utf-8') as fo:
        for xsams_chunk in xsams_xsec_chunk(NODEID, id, comment,
                            sources, T, isotopologue, numin, numax,
                            dnu, sigma_name):
            print(xsams_chunk, file=fo)

def yield_xsams(NODEID, id, comment, sources, T, isotopologue, numin,
                numax, dnu, sigma_name=None, sigma=[]):
    for xsams_chunk in xsams_xsec_chunk(NODEID, id, comment,
                        sources, T, isotopologue, numin, numax,
                        dnu, sigma_name, sigma):
        yield xsams_chunk


