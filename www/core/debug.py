from django.db import connection
from django.conf import settings

class SqlPrintingMiddleware(object):
    def process_response(self, request, response):
        if len(connection.queries) > 0 and settings.DEBUG:
            for query in connection.queries:
                print query
        return response
