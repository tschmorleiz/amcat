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

from django.core.urlresolvers import reverse

from navigator.views.projectview import ProjectViewMixin
from amcat.models import Article
from django.views.generic.base import TemplateView
from amcat.tools import xtas
from amcat.nlp import naf

def get_result(article, methodlist):
    methods = []
    for method in methodlist.split("+"):
        if ";" in method:
            method, arg = method.split(";", 1)
        else:
            method, arg = method, ""
        methods.append((method, arg))
    return xtas.process_document(article, *methods)
    

class XTasView(ProjectViewMixin, TemplateView):
    template_name = "navigator/xtas.html"
    
    def get_context_data(self, article_id, methodlist, **kwargs):
        ctx = super(XTasView, self).get_context_data(**kwargs)
        a = Article.objects.get(pk=int(article_id))
        na = naf.NAF_Article.from_json(get_result(a, methodlist))

        sentences = []
        for sid in na.sentence_ids:
            words = " ".join(w.word for w in na.words if w.sentence_id == sid)
            sentences.append((sid, "", words))

        
        ctx.update(**locals())
        return ctx
