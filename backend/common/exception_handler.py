import logging

from django.db.models import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from common.enums import CodeEnum

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        logger.warning(f"受保护对象删除被拒: {exc}")
        return Response(
            {
                "success": False,
                "code": CodeEnum.PARAM_ERROR.code,
                "message": "该数据已被课表/任课引用，无法删除，请改为停用",
                "data": None,
            },
            status=400,
        )

    # 第一路：主动抛出的业务异常 → 项目指南/后端/2.统一响应体系.md §异常处理器
    if hasattr(exc, "code"):
        logger.warning(
            f"业务异常: code={exc.code}, message={exc.message}, "
            f"path={context['request'].path}"
        )
        response = Response(
            {
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
            }
        )
        response.status_code = exc.http_status
        return response

    # 第二路：框架自动抛出的异常
    response = exception_handler(exc, context)

    if response is not None:
        error_messages = _extract_error_messages(response.data)
        status_code = response.status_code

        code_map = {
            401: CodeEnum.TOKEN_INVALID,
            403: CodeEnum.PERMISSION_DENIED,
            404: CodeEnum.NOT_FOUND,
            405: CodeEnum.METHOD_NOT_ALLOWED,
            400: CodeEnum.PARAM_ERROR,
        }

        code_enum = code_map.get(status_code, CodeEnum.PARAM_ERROR)

        logger.warning(
            f"框架异常: status={status_code}, message={error_messages}, "
            f"path={context['request'].path}"
        )

        response.data = {
            "success": False,
            "code": code_enum.code,
            "message": error_messages[0] if error_messages else code_enum.message,
            "data": None,
        }
        return response

    # 第三路：未预料的异常 → 500
    logger.error(
        f"未处理异常: {type(exc).__name__}: {exc}, "
        f"path={context['request'].path}"
    )
    return Response(
        {
            "success": False,
            "code": CodeEnum.SERVER_ERROR.code,
            "message": CodeEnum.SERVER_ERROR.message,
            "data": None,
        },
        status=500,
    )


def _extract_error_messages(data):
    messages = []
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                messages.extend(str(v) for v in value)
            elif isinstance(value, dict):
                messages.extend(_extract_error_messages(value))
            else:
                messages.append(str(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                messages.extend(_extract_error_messages(item))
            else:
                messages.append(str(item))
    else:
        messages.append(str(data))
    return messages
