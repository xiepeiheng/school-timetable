from enum import Enum


# 统一错误码枚举 → 项目指南/后端/2.统一响应体系.md §错误码枚举
class CodeEnum(Enum):
    OK = (200, "操作成功")
    PARAM_ERROR = (4000, "参数错误")
    USER_NOT_LOGIN = (4010, "用户未登录")
    TOKEN_INVALID = (4011, "Token 无效或已过期")
    USER_DISABLED = (4012, "账号已被停用")
    PERMISSION_DENIED = (4030, "没有操作权限")
    NOT_FOUND = (4040, "资源不存在")
    METHOD_NOT_ALLOWED = (4050, "请求方法不允许")
    SERVER_ERROR = (5000, "服务器内部错误")

    @property
    def code(self):
        return self.value[0]

    @property
    def message(self):
        return self.value[1]
