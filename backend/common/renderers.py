from rest_framework.renderers import JSONRenderer
from common.enums import CodeEnum


# 响应最后一关，统一所有成功响应的格式 → 项目指南/后端/2.统一响应体系.md §渲染器
class UnifiedJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            data = {}

        response = renderer_context.get("response")

        if response and 200 <= response.status_code < 400:
            # DRF 的 destroy 默认 204 无 body，无法包装；统一改为 200 走成功信封
            if response.status_code == 204:
                response.status_code = 200
                data = {"message": "删除成功"}

            if isinstance(data, dict) and "success" in data:
                return super().render(data, accepted_media_type, renderer_context)

            if isinstance(data, dict) and "data" in data:
                return super().render(
                    {
                        "success": True,
                        "code": CodeEnum.OK.code,
                        "message": data.get("message", CodeEnum.OK.message),
                        "data": data["data"],
                    },
                    accepted_media_type,
                    renderer_context,
                )

            message = CodeEnum.OK.message
            if isinstance(data, dict) and "message" in data:
                message = data["message"]
                del data["message"]

            data = {
                "success": True,
                "code": CodeEnum.OK.code,
                "message": message,
                "data": data,
            }

        return super().render(data, accepted_media_type, renderer_context)
