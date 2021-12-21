# Standard Library
import threading
import copy
import logging
from django.conf import settings
import time


# logger = logging.getLogger('request_logger')


class RequestMiddleware(object):
    """Class for getting the current request"""

    _requestdata = {}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # if settings.DEBUG:
        #     start_time = time.time()

        self._requestdata["body_data"] = copy.copy(request.body)  # copy.copy(request.body.decode("utf-8"))
        self._requestdata[threading.current_thread()] = request
        response = self.get_response(request)
        self._requestdata.pop(threading.current_thread(), None)

        # if settings.DEBUG:
        #     duration = time.time() - start_time
        #     logger.debug({
        #         "message": "request",
        #         "path": str(getattr(request, 'path', '')),
        #         "method": str(getattr(request, 'method', '')).upper(),
        #         "user": str(getattr(request, 'user', '')),
        #         "body": str(getattr(request, 'body', '')),
        #         "headers": str(getattr(request, 'headers', '')),
        #     })
        #     response_ms = duration * 1000
        #     status_code = str(getattr(response, 'status_code', ''))
        #     logger.debug({
        #         "message": "response",
        #         "response_time": str(response_ms) + " ms",
        #         "status_code": status_code,
        #         "data": str(getattr(response, 'data', ''))
        #     })

        return response

    @classmethod
    def get_request_data(cls, default=None):
        """returns the current request and data"""
        return (
            cls._requestdata.get("body_data", None),
            cls._requestdata.get(threading.current_thread(), default),
        )
