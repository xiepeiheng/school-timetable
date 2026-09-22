from common.enums import CodeEnum


class APIException(Exception):
    def __init__(self, code_enum=None, http_status=None, message=None, data=None):
        self.code_enum = code_enum or CodeEnum.PARAM_ERROR
        self.code = self.code_enum.code
        self.http_status = http_status or 400
        self.message = message or self.code_enum.message
        self.data = data
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}"


class BusinessException(APIException):
    pass


class AuthenticationException(APIException):
    def __init__(self, code_enum=CodeEnum.USER_NOT_LOGIN, message=None):
        super().__init__(code_enum, http_status=401, message=message)


class PermissionException(APIException):
    def __init__(self, code_enum=CodeEnum.PERMISSION_DENIED, message=None):
        super().__init__(code_enum, http_status=403, message=message)


class NotFoundException(APIException):
    def __init__(self, code_enum=CodeEnum.NOT_FOUND, message=None):
        super().__init__(code_enum, http_status=404, message=message)
