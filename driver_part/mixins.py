from rest_framework.response import Response

class StandardResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # Only format successful responses
        if 200 <= response.status_code < 300:
            response.data = {
                "status": True,
                "message": "success",
                "data": response.data
            }
        else:
            # Format errors
            response.data = {
                "status": False,
                "message": response.data.get("detail", "error"),
                "data": None
            }
        return response
