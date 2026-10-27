from django.http import Http404
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin


class FriendlyHttp404Middleware(MiddlewareMixin):
    """Render the branded 404 page for Http404 exceptions, including in DEBUG mode.

    MiddlewareMixin provides the get_response-compatible constructor and callable
    interface required by Django's MIDDLEWARE setting.
    """

    def process_exception(self, request, exception):
        if isinstance(exception, Http404):
            return render(request, "errors/404.html", status=404)
        return None
