import json
from django.http import HttpResponse
from amcat.models import Article

from rest_framework import views
from amcat.tools import xtas

class XTasResource(views.APIView):
    def get(self, request, *args, **kwargs):
        methods = request.GET.getlist('method')
        if not methods:
            raise Exception("Please specify a method")
        methods = [m.split(",") for m in methods]
        a = Article.objects.get(pk=kwargs["article"])
        result = xtas.process_document_sync(a, *methods)
        return HttpResponse(result, content_type="application/json")

    def get_url_pattern(cls):
        """The url pattern for use in the django urls routing table"""
        pattern = ArticleViewSet.url + "/(?P<article>[0-9]+)/process"
        return url(pattern, cls.as_view(), name="xtas")
