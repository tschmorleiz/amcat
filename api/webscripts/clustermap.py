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

from webscript import WebScript

from amcat.scripts.processors.clustermap import (ClustermapScript,
                                                 ClustermapTableScript)
import amcat.scripts.forms
from amcat.tools import keywordsearch

import logging
log = logging.getLogger(__name__)

class ClusterMapForm(amcat.scripts.forms.InlineTableOutputForm):
    pass

class ShowClusterMap(WebScript):
    name = "ClusterMap"
    form_template = None
    form = ClusterMapForm
    output_template = 'api/webscripts/clustermap.html'
    solrOnly = True
    displayLocation = ('ShowSummary','ShowArticleList')


    def run(self):
        form = self.data.copy()
        articleidDict = dict(keywordsearch.get_ids_per_query(form))
        
        if self.output == 'html' or self.output == 'json-html':
            result = ClustermapScript(self.data).run(articleidDict)
            outputType = ClustermapScript.output_type
        else:
            result = ClustermapTableScript(self.data).run(articleidDict)
            outputType = ClustermapTableScript.output_type
        return self.outputResponse(result, outputType)
