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
Syntax tree represented in RDF
"""
import re
from collections import namedtuple, defaultdict
from itertools import chain
from amcat.models import AnalysisSentence, Label
import logging
log = logging.getLogger(__name__)

from rdflib import ConjunctiveGraph, Namespace, Literal
AMCAT = "http://amcat.vu.nl/amcat3/"
NS_AMCAT = Namespace(AMCAT)
VIS_IGNORE_PROPERTIES = "position", "label"

Triple = namedtuple("Triple", ["subject", "predicate","object"])
from amcat.tools import dot

class Node(object):
    """Flexible 'record-like' object with arbitrary attributes used for representing tokens"""
    def __unicode__(self):
        return "Node(%s)" % ", ".join("%s=%r"%kv for kv in self.__dict__.iteritems())
    def __init__(self, **kargs):
        self.__dict__.update(kargs)
    __repr__ = __unicode__
    
class SyntaxTree(object):

    def __init__(self, soh, sentence_or_tokens=None):
        self.soh = soh
        self.soh.prefixes[""] = AMCAT
        if sentence_or_tokens:
            self.load_sentence(sentence_or_tokens)

    def load_sentence(self, rdf_triples):
        """
        Load the triples for the given analysis sentence into the triple store
        """
        g = ConjunctiveGraph()
        g.bind("amcat", AMCAT)
        from amcat.tools import djangotoolkit
        for triple in rdf_triples:
            g.add(triple)
        self.soh.add_triples(g, clear=True)



    def get_triples(self, ignore_rel=True, filter_predicate=None):
        """Retrieve the Node-predicate_string-Node triples for the loaded sentence"""
        if isinstance(filter_predicate, (str, unicode)):
            filter_predicate = [filter_predicate]
        nodes = {}
        for s,p,o in self.soh.get_triples(parse=True):
            child = nodes.setdefault(s, Node())
            pred = str(p).replace(AMCAT, "")
            if isinstance(o, Literal):
                if hasattr(child, pred):
                    o = getattr(child, pred) + "; " + o
                setattr(child, pred, unicode(o))
            else:
                if ignore_rel and pred == "rel": continue
                if filter_predicate and pred not in filter_predicate: continue
                if pred == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": continue
                parent = nodes.setdefault(o, Node())
                yield Triple(child, pred, parent)
    
    def visualise(self, **kargs):
        return visualise_triples(list(self.get_triples()), **kargs)

    def apply_ruleset(self, ruleset):
        self.apply_lexicon(ruleset)
        for rule in ruleset.rules.all():
            self.apply_rule(rule)
    
    def apply_rule(self, rule):
        """Apply the given amcat.models.rule.Rule"""
        self.soh.update(rule.where, rule.insert, rule.remove)

    def get_tokens(self):
        tokens = defaultdict(dict) # id : {attrs}
        for s,p,o in self.soh.get_triples(parse=True):
            if p == NS_AMCAT["lemma"]:
                tokens[s]["lemma"] = o
        return tokens
        
    def apply_lexicon(self, ruleset):
        lexicon = ruleset.lexicon
        lexicon = {"say" : ["test"]}
        for token_id, attrs in self.get_tokens().iteritems():
            for lemma, lexclasses in lexicon.iteritems():
                if lexical_match(lemma, attrs):
                    self.apply_lexical_entry(token_id, lexclasses)
                    
    def apply_lexical_entry(self, token_id, lexclasses):
        uri = str(token_id).replace(AMCAT, ":")
        insert = "\n;   ".join(':lexclass "{lexclass}"'.format(**locals()) for lexclass in lexclasses)
        self.soh.update(insert='{uri} {insert}'.format(**locals()))

                    
def lexical_match(lemma, attrs):
    l = attrs['lemma']
    if l == lemma: return True
    if lemma.endswith("*") and l.startswith(lemma[:-1]): return True
                    

        
def _id(obj):
    return obj if isinstance(obj, int) else obj.id
    
def _term_uri(term):
    tokenstr = re.sub("\W", "", term.lemma.encode("ascii", "ignore"))
    uri = NS_AMCAT["t_{term.term_id}_{tokenstr}".format(**locals())]
    return uri
def _rel_uri(rel):
    return NS_AMCAT["rel_{rel.rfunc}".format(**locals())]

def _naf_to_rdf(naf_article, sentence_id):
    """
    Get the raw RDF subject, predicate, object triples representing the given analysed sentence
    """
    # token literals
    triples = set()
    words = {w.word_id : w for w in naf_article.words if w.sentence_id == sentence_id}

    term_uris = {} # tid : uri
    for term in naf_article.terms:
        uri = _term_uri(term)
        twords = [words[wid]  for wid in term.word_ids if wid in words]
        if not twords: continue # wrong sentences
        
        yield uri, NS_AMCAT["label"], Literal(",".join(t.word for t in twords))
        yield uri, NS_AMCAT["lemma"], Literal(term.lemma)
        yield uri, NS_AMCAT["pos"], Literal(term.pos)
        yield uri, NS_AMCAT["position"], Literal(str(twords[0].offset))
        term_uris[term.term_id] = uri

    for dep in naf_article.dependencies:
        if dep.to_term in words:
            child = term_uris[dep.from_term]
            parent = term_uris[dep.to_term]            
            for pred in _rel_uri(dep), NS_AMCAT["rel"]:
                yield parent, pred, child

    for i, f in enumerate(naf_article.fixed_frames):
        if f["target"][0] in words:
            uri = NS_AMCAT["frame_{i}_{fname}".format(fname=f["name"], **locals())]
            yield uri, NS_AMCAT["position"], Literal(1000+i)
            yield uri, NS_AMCAT["label"], Literal(f["name"])
            yield uri, NS_AMCAT["frame"], Literal(f["name"])

            
            for term in f["target"]:
                yield uri, NS_AMCAT["frame_predicate"], term_uris[term]
            for e in f["elements"]:
                rel_uri = NS_AMCAT["frame_{ename}".format(ename=e["name"])]
                for term in e["target"]:
                    yield uri, rel_uri,  term_uris[term]
                    
                
def visualise_triples(triples,  triple_args_function=None, ignore_properties=VIS_IGNORE_PROPERTIES):
    """
    Visualise a triples representation of Triples such as retrieved from
    TreeTransformer.get_triples
    """
    g = dot.Graph()
    nodes = {} # Node -> dot.Node
    # create nodes
    nodeset = set(chain.from_iterable((t.subject, t.object) for t in triples))
    for n in nodeset:
        label = "%s: %s" % (n.position, n.label)
        for k,v in n.__dict__.iteritems():
            if k not in ignore_properties:
                label += "\\n%s: %s" % (k, v)
        node = dot.Node(id="node_%s"%n.position, label=label)
        g.addNode(node)
        nodes[n] = node
    # create edges
    for triple in triples:
        kargs = triple_args_function(triple) if  triple_args_function else {}
        if 'label' not in kargs: kargs['label'] = triple.predicate
        g.addEdge(nodes[triple.subject], nodes[triple.object], **kargs)
    # some theme options
    g.theme.graphattrs["rankdir"] = "BT"
    g.theme.shape = "rect"
    g.theme.edgesize = 10
    g.theme.fontsize = 10

    return g
