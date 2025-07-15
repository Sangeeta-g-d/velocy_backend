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
            message = "error"
            if isinstance(response.data, dict):
                if "detail" in response.data:
                    message = response.data["detail"]
                else:
                    error_list = []
                    for field, errors in response.data.items():
                        if isinstance(errors, list):
                            for error in errors:
                                error_list.append(f"{field}: {error}")
                        elif isinstance(errors, dict):  # nested serializer case
                            for subfield, suberror in errors.items():
                                error_list.append(f"{field}.{subfield}: {suberror}")
                        else:
                            error_list.append(f"{field}: {errors}")
                    message = " | ".join(error_list)

            response.data = {
                "status": False,
                "message": message,
                "data": None
            }
        return response
