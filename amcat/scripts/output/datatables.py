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

from amcat.tools.table import table3
from amcat.scripts import script, types
import json
from django import forms
import datetime
from amcat.tools.toolkit import writeDateTime


class DataTableForm(forms.Form):
    sEcho = forms.IntegerField(required=False)


import logging
log = logging.getLogger(__name__)


def _default_json(obj):
    if not isinstance(obj, datetime.datetime):
        return unicode(obj)
    return writeDateTime(obj, year=True, seconds=False, time=False)


class TableToDatatable(script.Script):
    input_type = table3.Table
    options_form = DataTableForm
    output_type = types.DataTableJsonData

    def run(self, tableObj):
        tableData = []
        for row in tableObj.getRows():
            rowList = []
            for column in tableObj.getColumns():
                rowList.append(tableObj.getValue(row, column))
            tableData.append(rowList)

        tableColumns = [{'sTitle': column, 'sName': column} for column in tableObj.getColumns()]

        dictObj = {}
        dictObj['aaData'] = tableData
        dictObj['aoColumns'] = tableColumns
        dictObj['iTotalRecords'] = 9999
        dictObj['iTotalDisplayRecords'] = 9999 if len(tableData) > 0 else 0
        dictObj['sEcho'] = self.options['sEcho']

        return json.dumps(dictObj, default=_default_json)
