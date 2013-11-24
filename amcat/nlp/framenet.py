import os.path
from lxml import etree
import logging
log = logging.getLogger(__name__)
NS = {'namespaces' : {'fn': 'http://framenet.icsi.berkeley.edu'}}

_POS_MAP = {'jj' : 'a', 'nn' : 'n'}

def map_pos(pos):
    pos = pos.lower()
    if pos.startswith('v'): return 'v'
    return _POS_MAP[pos]

class FrameNet(object):
    def __init__(self, framenet_home=None):
        self.framenet_home = framenet_home if framenet_home is not None else os.environ["FRAMENET_HOME"]

    def get_frame(self, name):
        name = (name[0].upper() + name[1:].lower()).replace(" ","_")
        return Frame(self, self.get_fn("frame", name))

    def get_fn(self, folder, name):
        fn = os.path.join(self.framenet_home, folder, ".".join([name, "xml"]))
        if not os.path.exists(fn): raise ValueError("Cannot find {name} -> {fn}".format(**locals()))
        return fn

    def fix_frames(self, naf_article):
        for frame in naf_article.frames:
            term = naf_article.term(frame["target"][0])
            name = frame["name"]
            try:
                lu = self.get_frame(name).get_lexical_unit(term.lemma, term.pos)
            except ValueError:
                log.exception("Cannot get lexical unit")
                continue
            match = lu.get_elements(naf_article, term)
            elements = [dict(name=el, target=[t.term_id]) for (el, t) in match.iteritems()]
            
            yield dict(name= name,
                       target=[term.term_id],
                       elements=elements)
                   
class Frame(object):
    def __init__(self, framenet, fn):
        self.framenet = framenet
        self.fn = fn
        self._xml = None

    @property
    def xml(self):
        if self._xml is None:
            self._xml = etree.parse(open(self.fn))
        return self._xml
        
    def get_lexical_units(self):
        for u in self.xml.findall("fn:lexUnit", **NS):
            yield LexicalUnit(self, self.framenet.get_fn("lu", "lu{id}".format(id=u.attrib["ID"])))

    def get_lexical_unit(self, lemma, pos):
        if len(pos) > 1:
            pos = map_pos(pos)
        else:
            pos = pos.lower()
            
        name = "{lemma}.{pos}".format(lemma=lemma.lower(), pos=pos.lower())
        for u in self.xml.findall("fn:lexUnit", **NS):
            if u.attrib["name"] == name: 
                return LexicalUnit(self, self.framenet.get_fn("lu", "lu{id}".format(id=u.attrib["ID"])))
        raise ValueError("Can't find lu {name}".format(**locals()))

        
class LexicalUnit(object):
    def __init__(self, frame, fn):
        self.frame = frame
        self.fn = fn
        self._xml = None
        
    @property
    def xml(self):
        if self._xml is None:
            self._xml = etree.parse(open(self.fn))
        return self._xml

    @property
    def lexeme(self):
        l = self.xml.find("fn:lexeme", **NS)
        return l.attrib["name"], l.attrib["POS"]
    
    def get_fe_patterns(self):
        for p in self.xml.findall("//fn:FERealization/fn:pattern", **NS):
            vu = p.find("fn:valenceUnit", **NS)
            yield vu.attrib["FE"], vu.attrib["PT"], vu.attrib["GF"], int(p.attrib["total"])
            
        
    def get_fe_groups(self):
        for p in self.xml.findall("//fn:FEGroupRealization/fn:pattern", **NS):
            group = {}
            for vu in p.findall("fn:valenceUnit", **NS):
                fe, pt, gf = vu.attrib["FE"], vu.attrib["PT"], vu.attrib["GF"]
                group[fe] = (pt, gf)
            yield group, int(p.attrib["total"])
        
    def get_elements(self, naf_article, naf_term):
        """
        Return the best matching elements for this frame in the given naf_term in the naf_article
        """
        children = {d.rfunc: naf_article.term(d.to_term) for d in naf_article.get_children(naf_term)}

        # try whole-group match first, otherwise pick best match per-element
        match = self.best_group(children)
        if not match:
            match = dict(self.best_elements(children))
        return match
    
    def best_group(self, children):
        "Sort groups on length, frequency, return first fully matched group"
        def group_score(group):
            elements, n = group
            n_elements = len([1 for (pos, rel) in elements.values() if pos not in SKIP_POS])
            return -n_elements, -n
    
        groups = [g for g in self.get_fe_groups() if len(g[0]) > 1]
        groups = sorted(groups, key=group_score)#lambda g: (-len(g[0]), -g[1]))
        for group in groups: print(group)
        for (group, n) in groups:
            m = match_group(children, group)
            if m:
                return m

    def best_elements(self, children):
        "traverse elements in descending frequency, pick first hit per child"
        for (cat, pos, rel, n) in sorted(self.get_fe_patterns(), key=lambda p : -p[3]):
            m = match_pattern(children, pos, rel)
            if m:
                yield cat, m
                log.info("Found {cat} in {pos}.{rel} for term {m.lemma}".format(**locals()))
                # remove child from children
                children = {k : v for (k,v) in children.iteritems() if v != m}
            
### MATCHING POS/REL TO STANFORD RELATIONS
        
SKIP_POS = ['CNI', 'INI', '2nd', 'Sinterrog']
FRAMENET_TO_STANFORD = {
    ('PP', 'Dep') : ['prep'],
    ('PPing', 'Dep') : ['prepc'],
    ('NP', 'Ext') : ['nsubjpass', 'nsubj'],
    ('NP', 'Obj') : ['dobj'],
    ('NP', 'Dep') : ['tmod', 'nn'],
    ('Poss', 'Gen') : ['poss'],
    ('AJP', 'Dep') : ['amod'],
    ('AVP', 'Dep') : ['advmod'],
    ('Sub', 'Dep') : ['advcl'],
    ('Sfin', 'Dep') : ['ccomp'],
    }
import re
RE_PP = re.compile(r'(\w+)\[(\w+)\]')

def match_pattern(children, pos, rel):
    # skip non-instantiated
    if pos in SKIP_POS: return
    # Deal with pp[as]
    m = RE_PP.match(pos)
    if m:
        pos, suffix = m.groups()
    else:
        suffix = None
    # NP and N are the same for us
    if pos == 'N': pos = 'NP'
    # try to match stanford candidates from dict
    for candidate in FRAMENET_TO_STANFORD[pos, rel]:
        if suffix:
            candidate = "{candidate}_{suffix}".format(**locals())
        if candidate in children:
            return children[candidate]
            
def match_group(children, group):
    result = {}
    for cat, (pos, rel) in group.iteritems():
        m = match_pattern(children, pos, rel)
        if m:
            result[cat] = m
        elif pos not in SKIP_POS:
            log.info("Missing element {pos}.{rel} in group {group}".format(**locals()))
            return
    return result     

###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest

class TestFrameNet(amcattest.PolicyTestCase):
    def test_get_frame(self):
        f = FrameNet().get_frame("finish competition")
        self.assertRaises(ValueError, FrameNet().get_frame, "bla")
        
        lu = f.get_lexical_unit("victory", "n")
        self.assertRaises(ValueError, f.get_lexical_unit, "bla", "bla")
        
        self.assertEqual(lu.lexeme, ("victory", "N"))
        self.assertEqual(len(list(lu.get_fe_patterns())), 20)
        self.assertIn(("Competitor", "PP[for]", "Dep", 4), set(lu.get_fe_patterns()))
        
        self.assertEqual(len(list(lu.get_fe_groups())), 30)
        self.assertIn((dict(Competition=("N", "Dep"), Competitor=("Poss", "Gen")),4), list(lu.get_fe_groups()))
