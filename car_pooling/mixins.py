from rest_framework.response import Response

class StandardResponseMixin:
    def response(self, data=None, status_code=200):
        return Response(data, status=status_code)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        if 200 <= response.status_code < 300:
            response.data = {
                "status": True,
                "message": "success",
                "data": response.data
            }
        else:
            if isinstance(response.data, dict):
                message = response.data.get("detail") or next(iter(response.data.values()))[0]
            else:
                message = "error"

            response.data = {
                "status": False,
                "message": message,
                "data": None
            }

        return response
