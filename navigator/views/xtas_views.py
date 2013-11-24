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

import collections

from django.core.urlresolvers import reverse

from navigator.views.projectview import ProjectViewMixin
from amcat.models import Article
from django.views.generic.base import TemplateView
from amcat.tools import xtas
from amcat.tools.table import table3, tableoutput
from amcat.nlp import naf, syntaxtree
from amcat.tools.pysoh.pysoh import SOHServer

def get_result(article, methodlist):
    methods = []
    for method in methodlist.split("+"):
        if ";" in method:
            method, arg = method.split(";", 1)
        else:
            method, arg = method, ""
        methods.append((method, arg))
    r = xtas.process_document_sync(article, *methods, force_resend=True)
    return r
    

class XTasView(ProjectViewMixin, TemplateView):
    template_name = "navigator/xtas.html"
    
    def get_context_data(self,projectid, article_id, methodlist, **kwargs):
        ctx = super(XTasView, self).get_context_data(**kwargs)
        a = Article.objects.get(pk=int(article_id))
        na = naf.NAF_Article.from_json(get_result(a, methodlist))

        sentences = []
        for sid in na.sentence_ids:
            words = " ".join(w.word for w in na.words if w.sentence_id == sid)
            url = reverse('xtas-sentence', args=(projectid, article_id, methodlist, sid))
            sentences.append((sid, url, words))

        
        ctx.update(**locals())
        return ctx

class FrameColumn(table3.ObjectColumn):
    def __init__(self, frame, prefix="Frame: "):
        super(FrameColumn, self).__init__(label = prefix + frame["name"])
        self.funcs = collections.defaultdict(list)
        for d in [frame] + frame["elements"]:
            for word_id in d["target"]:
                self.funcs[word_id].append(d["name"])
                
    def getCell(self, term):
        func = []
        for wid in term.word_ids:
            func += self.funcs[wid]
        return ",".join(func)
        
class XTasSentenceView(ProjectViewMixin, TemplateView):
    template_name = "navigator/xtas_sentence.html"
    
    def get_context_data(self, article_id, methodlist, sentence_id, **kwargs):
        ctx = super(XTasSentenceView, self).get_context_data(**kwargs)
        a = Article.objects.get(pk=int(article_id))
        na = naf.NAF_Article.from_json(get_result(a, methodlist))
        sentence_id = int(sentence_id)
        words = {w.word_id : w for w in na.words if w.sentence_id == sentence_id}
        terms = [t for t in na.terms if any(w in words for w in t.word_ids)]
        deps = [d for d in na.dependencies if d.to_term in words]

        elements = [k for (k, v) in na.__dict__.iteritems() if v]
        
        token_table = table3.ObjectTable(rows=terms)
        token_table.addColumn(lambda t:t.term_id, "term id")
        token_table.addColumn(lambda t:",".join(str(wid) for wid in t.word_ids), "word id(s)")
        token_table.addColumn(lambda t:",".join(str(words[wid].offset) for wid in t.word_ids), "offset(s)")
        token_table.addColumn(lambda t:",".join(words[wid].word for wid in t.word_ids), "word(s)")
        token_table.addColumn(lambda t:t.lemma, "lemma")
        token_table.addColumn(lambda t:t.pos, "pos")

        frames = [f for f in na.frames if f["sentence_id"] == sentence_id]
        for f in frames:
            token_table.addColumn(FrameColumn(f))
            

        frames = [f for f in na.fixed_frames if f["sentence_id"] == sentence_id]
        for f in frames:
            token_table.addColumn(FrameColumn(f, "Fixed Frame: "))

        token_table = tableoutput.table2html(token_table, printRowNames=False)
            
        rdf = list(syntaxtree._naf_to_rdf(na, sentence_id))

        soh = SOHServer(url="http://localhost:3030/x")
        tree = syntaxtree.SyntaxTree(soh, rdf)
        parsetree = tree.visualise().getHTMLObject()
        
        ctx.update(**locals())
        return ctx
