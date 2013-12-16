###########################################################################
#          (C) Vrije Universiteit, Amsterdam (the Netherlands)            #
#                                                                         #
# This file is part of AmCAT - The Amsterdam Content Analysis Toolkit     #
#                                                                         #
# AmCAT is free software: you can redistribute it and/or modify it under  #
# the terms of the GNU Affero General Public License as published by the  #
# Free Software Foundation, either version 3 of the License, or (at your  #
# option) any later version.                                              #
#                                                                         #
# AmCAT is distributed in the hope that it will be useful, but WITHOUT    #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or   #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public     #
# License for more details.                                               #
#                                                                         #
# You should have received a copy of the GNU Affero General Public        #
# License along with AmCAT.  If not, see <http://www.gnu.org/licenses/>.  #
###########################################################################

"""
Classes that represent NAF primitives as a named tuple with a final 'extra' argument.
"""

from collections import namedtuple
import json
from lxml import etree

def element(tag, parent=None,text=None, **attrs):
    """Helper method to create an element with parent and/or text and/or attributes"""
    attrs = {k : unicode(v) for (k,v) in attrs.iteritems()}
    t = etree.Element(tag, **attrs)
    if parent is not None:
        parent.append(t)
    if text:
        t.text = unicode(text)
    return t
    
class NAF_Object(object):
    tag = None
    text_attr = None
    ignore_attrs = None
    attr_map = None
    
    def __new__(self, *args, **kargs):
        if "extra" in self._fields:
            if "extra" not in kargs:
                kargs["extra"] = {}
            for k in list(kargs):
                if k not in self._fields:
                    kargs["extra"][k] = kargs.pop(k)
            # merge 'args' extra with 'kargs' extra
            if len(args) == len(self._fields):
                kargs["extra"].update(args[-1])
                args = args[:-1]
            
        if len(args) + len(kargs) != len(self._fields):
            raise ValueError("Wrong number of arguments, expected {self._fields}, got {args} + {kargs}".format(**locals())) 
        return super(NAF_Object, self).__new__(self, *args, **kargs)
        
    def __getattr__(self, attr):
        if attr == "extra":
            raise AttributeError(attr)
        try:
            return self.extra[attr]
        except KeyError:
            raise AttributeError(attr)

    def generate_xml(self, parent=None):
        tag = self.tag or self.__class__.__name__
        fields = self.get_xml_fields()
        map = self.attr_map if self.attr_map is not None else {}
        kargs = {map.get(k,k): unicode(getattr(self, k)) for k in fields}
        text  = getattr(self, self.text_attr) if self.text_attr else None
        return element(tag, parent=parent, text=text, **kargs)

    def get_xml_fields(self):
        for f in self._fields:
            if f in ("extra", self.text_attr): continue
            if self.ignore_attrs and f in self.ignore_attrs: continue
            yield f

        if "extra" in self._fields:
            for f in self.extra.keys():
                yield f


class WordForm(NAF_Object, namedtuple("WordForm",
                                      ["word_id", "sentence_id", "offset", "word", "extra"])):
    tag = "wf"
    text_attr = "word"

class Term(NAF_Object, namedtuple("Term", ["term_id", "word_ids", "lemma", "pos", "extra"])):
    tag = "term"
    ignore_attrs = ["word_ids"]
    
    def generate_xml(self, parent=None):
        e = super(Term, self).generate_xml(parent)
        span = element("span", parent=e)
        for word_id in self.word_ids:
            element("target", parent=span, id=unicode(word_id))
        return e
        
class Entity(NAF_Object, namedtuple("Entity", ["entity_id", "term_ids", "type", "extra"])):
    pass
    
class Dependency(NAF_Object, namedtuple("Dependency",
                                        ["from_term", "to_term", "rfunc", "extra"])):
    tag = "dep"
    attr_map = {"from_term" : "from", "to_term" : "to"}

class Coreference(NAF_Object, namedtuple("Coreference", ["co_id", "spans"])):
    pass

class Coreference_target(NAF_Object, namedtuple("Coreference_target", ["term_id", "head"])):
    pass

class NAF_Article(object):
    def __init__(self):
        self.sentences = []
        self.words = []
        self.terms = []
        self.entities = []
        self.dependencies = []
        self.coreferences = []
        self.trees = []
        self.frames = []
        self.fixed_frames = []


    def term(self, term_id):
        for term in self.terms:
            if term.term_id == term_id:
                return term
        raise ValueError("Term {term_id} not found".format(**locals()))
        
    @property
    def sentence_ids(self):
        return sorted({wf.sentence_id for wf in self.words})
        
    def create_sentence(self):
        sentence_id = len(self.sentences)+1
        result = Sentence(self, sentence_id)
        self.sentences.append(result)
        return result
    def create_coreference(self, spans=None):
        co_id = len(self.coreferences) + 1
        if spans is None: spans = []
        co = Coreference(co_id, spans)
        self.coreferences.append(co)
        return co

    def generate_xml(self):
        root = etree.Element("NAF")
        text, terms, deps = [element(x, parent=root) for x in ["text", 'terms', "deps"]]
        [root.append(e) for e in [text, terms, deps]]
        [word.generate_xml(parent=text) for word in self.words]
        [term.generate_xml(parent=terms) for term in self.terms]
        [dep.generate_xml(parent=deps) for dep in self.dependencies]
        return root


    def to_json(self, **kargs):
        """
        Represent this article as a dict so it can be easily converted to json
        """
        d = {k : getattr(self, k) for k in ["words", "terms", "entities", "dependencies", "coreferences", "trees", "frames", "fixed_frames"]}
        
        return json.dumps(d, **kargs)

    @classmethod
    def from_json(cls, json_string):
        a = cls()
        d = json.loads(json_string)
        for attr, target_class in ("words", WordForm), ("terms", Term), ("entities", Entity), ("dependencies", Dependency):
            val = [target_class(*data) for data in d[attr]]
            setattr(a, attr, val)
        a.trees = d["trees"]
        a.frames = d.get("frames", [])
        a.fixed_frames = d.get("fixed_frames", [])
        a.coreferences = [Coreference_target(co_id, [[Coreference_target(*s) for s in targets]
                                                     for targets in spans])
                          for co_id, spans in d["coreferences"]]
        return a

    def get_children(self, term):
        if isinstance(term, Term): term = term.term_id
        for dep in self.dependencies:
            if dep.from_term == term:
                yield dep
    
class Sentence(object):
    """
    Helper object. Sentences are not a NAF primitive, but since terms
    do require a sentence number (and in stanford many references are
    to indices within a sentence) it is helpful for constructing the NAF objects.
    """
    def __init__(self, article, sentence_id):
        self.article = article
        self.sentence_id = sentence_id
        self.terms = [] # to offer index-based retrieval
        self.tree = None
        
    def add_word(self, offset, word, lemma, pos, entity_type=None):
        """
        Add a new word and term to this sentence (and hence article)
        Note, this call is NOT thread safe
        """
        word_id = len(self.article.words) + 1
        term_id = len(self.article.terms) + 1
        word = WordForm(word_id, self.sentence_id, offset, word)
        term = Term(term_id, [word_id], lemma, pos)
        self.article.words.append(word)
        self.article.terms.append(term)
        self.terms.append(term)
        if entity_type:
            entity_id = len(self.article.entities) + 1
            entity = Entity(entity_id, term_id, entity_type)
            self.article.entities.append(entity)
    def add_dependency(self, from_term, to_term, rfunc):
        dep = Dependency(from_term, to_term, rfunc)
        self.article.dependencies.append(dep)

###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest

class TestNAF(amcattest.AmCATTestCase):
    def test_wordform(self):
        w = WordForm(1,2,3,"test")
        self.assertEqual(w.word, "test")
        self.assertFalse(w.extra)
        self.assertRaises(AttributeError, getattr, w, "test")
        self.assertEqual(json.dumps(w), '[1, 2, 3, "test", {}]')

        w = WordForm(1,2,3,word="test", test1=1, test2="bla")
        self.assertEqual(w.word, "test")
        self.assertEqual(w.test1, 1)
        self.assertEqual(w.test2, "bla")
        self.assertEqual(json.dumps(w), '[1, 2, 3, "test", {"test1": 1, "test2": "bla"}]')

        
