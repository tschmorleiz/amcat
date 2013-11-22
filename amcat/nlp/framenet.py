import os.path
from lxml import etree

NS = {'namespaces' : {'fn': 'http://framenet.icsi.berkeley.edu'}}

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
