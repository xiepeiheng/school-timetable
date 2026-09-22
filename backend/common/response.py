from rest_framework.response import Response
from common.enums import CodeEnum


def success_response(data=None, message=None, code=None):
    return Response(
        {
            "success": True,
            "code": code or CodeEnum.OK.code,
            "message": message or CodeEnum.OK.message,
            "data": data,
        }
    )
