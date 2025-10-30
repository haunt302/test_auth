from functools import wraps

from django.http import JsonResponse


def require_access(resource_code, action):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if user is None or not user.is_authenticated:
                return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)
            if not user.has_permission(resource_code, action):
                return JsonResponse({'detail': 'Forbidden: missing permission.'}, status=403)
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator