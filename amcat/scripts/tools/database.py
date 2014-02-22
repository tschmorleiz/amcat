"""
A number of functions that help the Amcat3 selection page to retrieve selections from the database
"""

from amcat.models import ArticleSet, Project
from amcat.models import article
from django.db.models import Q
from amcat.tools.djangotoolkit import db_supports_distinct_on


def get_queryset(articlesets, mediums=None, start_date=None, end_date=None, article_ids=None, projects=None, **kargs):
    queryset = article.Article.objects
    queryset = queryset.filter(articlesets_set__in=articlesets)

    # Disabling filtering on medium if mediums equals all
    # articles in this project.
    if projects and len(projects) == 1:
        p = projects[0]
        if isinstance(p, int):
            p = Project.objects.get(id=p)

        if set(p.get_mediums().values_list("id")) == set(mediums.values_list("id")):
            mediums = None

    if mediums and "WHERE" in unicode(mediums.query):
        queryset = queryset.filter(medium__in=mediums)
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lt=end_date)
    if article_ids:
        queryset = queryset.filter(id__in=article_ids)

    if db_supports_distinct_on():
        return queryset.distinct("pk")
    return queryset.distinct()
