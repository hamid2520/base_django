from rest_framework.permissions import IsAuthenticated

from rest_framework.authentication import TokenAuthentication


class IsAuthenticatedPermission(object):
    authentication_classes = [
        TokenAuthentication
    ]
    permission_classes = [
        IsAuthenticated,
    ]
