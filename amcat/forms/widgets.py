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
Replacement for the standard Django forms.widgets module. It contains all
standard widgets plus extra (amcat-specific) widgets.
"""

from django.forms import widgets

__all__ = ["JQuerySelect", "JQueryMultipleSelect"]

class JQuerySelect(widgets.Select):
    def _build_attrs(self, attrs=None, **kwargs):
        attrs = dict() if attrs is None else attrs
        attrs.update(kwargs)
        return attrs

    def render(self, name, value, attrs=None):
        attrs = self._build_attrs(attrs, **{'class' : 'multiselect'})
        return super(JQuerySelect, self).render(name, value, attrs=attrs)
     
class JQueryMultipleSelect(JQuerySelect, widgets.SelectMultiple):
    def render(self, name, value, attrs=None, *args, **kwargs):
        attrs = self._build_attrs(attrs, multiple='multiple')
        return super(JQueryMultipleSelect, self).render(name, value, attrs=attrs)

def convert_to_jquery_select(form):
    for field in form.fields:
        print field,  type(form.fields[field].widget), type(form.fields[field].widget) == widgets.Select
        w = form.fields[field].widget
        if type(w) == widgets.Select:
            form.fields[field].widget = JQuerySelect(attrs=w.attrs, choices=w.choices)
