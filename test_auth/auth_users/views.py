import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.utils.decorators import method_decorator

from auth_users.decorators import require_access
from auth_users.forms import (
    AccountDeactivateForm,
    AuthenticationForm,
    ProfileUpdateForm,
    UserCreationForm,
)
from auth_users.models import Resource, Role, RolePermission, UserRole
from auth_users.utils import send_email_for_verify

User = get_user_model()


class MyLoginView(LoginView):
    form_class = AuthenticationForm


class EmailVerify(View):

    def get(self, request, uidb64, token):
        user = self.get_user(uidb64)

        if user is not None and token_generator.check_token(user, token):
            user.email_verify = True
            user.save()
            login(request, user)
            return redirect('home')
        return redirect('invalid_verify')

    @staticmethod
    def get_user(uidb64):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
            ValidationError
        ):
            user = None
        return user



class Register(View):
    template_name = 'registration/register.html'

    def get(self, request):
        context = {
            'form': UserCreationForm()
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = UserCreationForm(request.POST)

        if form.is_valid():
            form.save()
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password1')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                send_email_for_verify(request, user)
            return redirect('confirm_email')
        context = {
            'form': form
        }
        return render(request, self.template_name, context)
    

class ProfileView(LoginRequiredMixin, View):
    template_name = 'profile.html'

    def get(self, request):
        context = {
            'form': ProfileUpdateForm(instance=request.user),
            'deactivate_form': AccountDeactivateForm(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = ProfileUpdateForm(request.POST, instance=request.user)
        deactivate_form = AccountDeactivateForm(request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
        context = {'form': form, 'deactivate_form': deactivate_form}
        return render(request, self.template_name, context)


class AccountDeactivateView(LoginRequiredMixin, View):

    def post(self, request):
        form = AccountDeactivateForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            user.is_active = False
            user.save(update_fields=['is_active'])
            logout(request)
            return redirect('home')
        return render(
            request,
            'profile.html',
            {
                'form': ProfileUpdateForm(instance=request.user),
                'deactivate_form': form,
            },
        )


class AdminRequiredMixin:

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)
        if not user.is_administrator:
            return JsonResponse({'detail': 'Forbidden: administrator role required.'}, status=403)
        return super().dispatch(request, *args, **kwargs)


class RolePermissionManagementView(AdminRequiredMixin, View):

    def get(self, request):
        roles = Role.objects.prefetch_related('permissions__resource').all()
        data = []
        for role in roles:
            permissions = [
                {
                    'resource': perm.resource.code,
                    'action': perm.action,
                }
                for perm in role.permissions.all()
            ]
            data.append(
                {
                    'id': role.id,
                    'name': role.name,
                    'slug': role.slug,
                    'description': role.description,
                    'permissions': permissions,
                }
            )
        return JsonResponse({'roles': data})

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

        role_slug = payload.get('role')
        resource_code = payload.get('resource')
        action = payload.get('action')
        grant = payload.get('grant', True)
        if isinstance(grant, str):
            grant = grant.lower() in {'true', '1', 'yes'}

        if not all([role_slug, resource_code, action]):
            return JsonResponse({'detail': 'role, resource and action are required.'}, status=400)

        valid_actions = {choice[0] for choice in RolePermission._meta.get_field('action').choices}
        if action not in valid_actions:
            return JsonResponse({'detail': 'Invalid action supplied.'}, status=400)

        try:
            role = Role.objects.get(slug=role_slug)
        except Role.DoesNotExist:
            return JsonResponse({'detail': 'Role not found.'}, status=404)

        try:
            resource = Resource.objects.get(code=resource_code)
        except Resource.DoesNotExist:
            return JsonResponse({'detail': 'Resource not found.'}, status=404)

        if grant:
            RolePermission.objects.get_or_create(
                role=role,
                resource=resource,
                action=action,
            )
            return JsonResponse({'detail': 'Permission granted.'})

        deleted, _ = RolePermission.objects.filter(
            role=role,
            resource=resource,
            action=action,
        ).delete()
        if deleted:
            return JsonResponse({'detail': 'Permission revoked.'})
        return JsonResponse({'detail': 'Permission not found.'}, status=404)


class RoleAssignmentView(AdminRequiredMixin, View):

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

        user_email = payload.get('user')
        role_slug = payload.get('role')
        assign = payload.get('assign', True)
        if isinstance(assign, str):
            assign = assign.lower() in {'true', '1', 'yes'}

        if not all([user_email, role_slug]):
            return JsonResponse({'detail': 'user and role are required.'}, status=400)

        try:
            target_user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return JsonResponse({'detail': 'User not found.'}, status=404)

        try:
            role = Role.objects.get(slug=role_slug)
        except Role.DoesNotExist:
            return JsonResponse({'detail': 'Role not found.'}, status=404)

        if assign:
            UserRole.objects.get_or_create(user=target_user, role=role)
            return JsonResponse({'detail': 'Role assigned.'})

        deleted, _ = UserRole.objects.filter(user=target_user, role=role).delete()
        if deleted:
            return JsonResponse({'detail': 'Role revoked.'})
        return JsonResponse({'detail': 'Assignment not found.'}, status=404)


@method_decorator(require_access('projects', 'view'), name='dispatch')
class ProjectListView(View):

    def get(self, request):
        return JsonResponse({'projects': [
            {'id': 1, 'name': 'Intranet Upgrade', 'status': 'in_progress'},
            {'id': 2, 'name': 'Marketing Site Redesign', 'status': 'planning'},
        ]})


@method_decorator(require_access('reports', 'edit'), name='dispatch')
class ReportEditView(View):

    def get(self, request):
        return JsonResponse({'detail': 'Use POST to submit report updates.'})

    def post(self, request):
        return JsonResponse({'detail': 'Report updated successfully.'})
