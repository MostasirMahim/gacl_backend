from activity_log.tasks import log_activity_task
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from .tasks import send_otp_email
from .serializers import RegistrationSerializer, LoginSerializer, ForgetPasswordSerializer, VerifyOtpSerializer
from django.core.mail import send_mail
from random import randint
from .models import OTP
from rest_framework.authtoken.models import Token
from rest_framework import status
from .serializers import RegistrationSerializer, LoginSerializer, ForgetPasswordSerializer, ResetPasswordSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
import pdb
from .tasks import send_otp_mail_to_email
import environ
from datetime import timedelta
from .permissions import HasCustomPermission
from .serializers import *
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from account.utils.functions import clear_user_permissions_cache, add_no_cache_header_in_response, generate_random_token, set_blocking_system
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils.datastructures import MultiValueDict
from .utils.permissions_classes import RegisterUserPermission, GroupPermissionManagement, ViewAllUserPermission
from activity_log.utils.functions import request_data_activity_log
from .utils.rate_limiting_classes import LoginRateThrottle
from django.core.cache import cache
from core.utils.pagination import CustomPageNumberPagination
import logging
from django.db.models import Count
# set env
environ.Env.read_env()
env = environ.Env()
# Set logger
logger = logging.getLogger("myapp")
# Authentication views


class AccountRegistrationView(APIView):
    def post(self, request):
        """
        Register a new account with valid data. 
        """
        try:
            data = request.data
            serializer = RegistrationSerializer(data=data)
            if serializer.is_valid():
                remember_me = serializer.validated_data['remember_me']
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
                response = Response({
                    "code": 201,
                    "message": "Operation successful",
                    "status": "success",
                    "access_token": str(access_token),
                    "refresh_token": str(refresh)
                }, status=status.HTTP_201_CREATED)

                # Add headers to prevent caching
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
                # set cookie
                time_limit_for_cookie = 30 if remember_me == True else 7

                response.set_cookie(
                    settings.SIMPLE_JWT["AUTH_COOKIE"],
                    str(access_token),
                    httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                    secure=env("COOKIE_SECURE") == "True",
                    max_age=timedelta(
                        days=time_limit_for_cookie).total_seconds()
                )
                response.set_cookie(
                    settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                    str(refresh),
                    httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                    secure=env("COOKIE_SECURE") == "True",
                    max_age=timedelta(
                        days=time_limit_for_cookie).total_seconds()
                )

                return response
            else:
                return Response(
                    {
                        'status': "failed",
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.exception(str(e))
            return Response({'errors': {
                'server_error': [str(e)]
            }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AccountLoginLogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def get_throttles(self):
        """Apply throttle only for POST requests"""
        if self.request.method == "POST":
            return [LoginRateThrottle()]
        return []

    def post(self, request):
        """
        Login to an account with valid data.
        """
        try:
            ip = self.get_client_ip(request)
            cache_key = f"failed_login_attempts_{ip}"
            block_key = f"block_time_{ip}"
            block_time = cache.get(block_key)
            if block_time:
                return Response({
                    "code": 429,
                    "status": "failed",
                    "message": f"Try again in {block_time} seconds.",
                    "errors": {
                        "request": ["To many requests"]}, }, status=status.HTTP_429_TOO_MANY_REQUESTS,)

            data = request.data
            serializer = LoginSerializer(data=data)
            if serializer.is_valid():
                username = serializer.validated_data['username']
                password = serializer.validated_data['password']
                remember_me = serializer.validated_data['remember_me']
                user = get_user_model().objects.get(username=username)
                user.set_password(password)
                user.save()

                # Generate a new token on every login session
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token

                # Response with no-cache headers
                response = Response({
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": "Token was created successfully",
                    "access_token": str(access_token),
                    "refresh_token": str(refresh),
                    "must_change_password": user.must_change_password,
                }, status=status.HTTP_200_OK)

                # Add headers to prevent caching
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
                # set cookie
                time_limit_for_cookie = 30 if remember_me == True else 7
                response.set_cookie(
                    settings.SIMPLE_JWT["AUTH_COOKIE"],
                    str(access_token),
                    httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                    secure=env("COOKIE_SECURE") == "True",
                    max_age=timedelta(
                        days=time_limit_for_cookie).total_seconds()
                )
                response.set_cookie(
                    settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                    str(refresh),
                    httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                    secure=env("COOKIE_SECURE") == "True",
                    max_age=timedelta(
                        days=time_limit_for_cookie).total_seconds()
                )
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Logged in",
                    severity_level="info",
                    description="User logged in to the system",
                )
                #  Reset counters on successful login
                cache.delete(cache_key)
                cache.delete(block_key)
                return response

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Logged in failure",
                    severity_level="warning",
                    description="Tried to log in to the system but failed to login",
                )
                failed_attempts = cache.get(cache_key, 0) + 1
                print(failed_attempts)
                if int(failed_attempts) >= 10:
                    if int(failed_attempts) == 10:
                        set_blocking_system(
                            cache_key, failed_attempts, block_key)
                    elif int(failed_attempts) >= 11 and int(failed_attempts) <= 15:
                        cache.set(cache_key, failed_attempts)
                    elif int(failed_attempts) == 16:
                        set_blocking_system(
                            cache_key, failed_attempts, block_key)
                    elif int(failed_attempts) >= 17 and int(failed_attempts) <= 19:
                        cache.set(cache_key, failed_attempts)
                    else:
                        set_blocking_system(
                            cache_key, failed_attempts, block_key)
                else:
                    cache.set(cache_key, failed_attempts)

                return Response({
                    'code': status.HTTP_400_BAD_REQUEST,
                    'status': "failed",
                    'message': "Invalid request",
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error Occurred while login",
                severity_level="critical",
                description="Tried to log in to the system but failed to login",
            )
            return Response({'errors': {
                'code': status.HTTP_400_BAD_REQUEST,
                'status': "failed",
                'message': "Error occurred",
                'errors': {
                    "server_error": [str(e)]
                }
            }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        """
        Delete authorization cookie from the server cookie
        """
        try:
            response = Response(
                {'code': status.HTTP_200_OK,
                 'status': "success",
                 'message': "Logout successful", 'detail': "Logout successful"}, status=status.HTTP_200_OK)
            # Delete the 'auth_token' cookie
            response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE"])
            response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])

            # Add headers to prevent caching
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Logged out from system",
                severity_level="info",
                description="User logged out from system",
            )
            return response

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Failure while logout",
                severity_level="info",
                description="User tried to logout but failure occurred",
            )
            return Response({'errors': {
                'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'status': "failed",
                'message': "Error occurred",
                'errors': {
                    "server_error": [str(e)]
                }
            }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ForgetPasswordView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
            Set OTP to the OTP model if user with email exist
        """
        data = request.data
        serializer = ForgetPasswordSerializer(
            data=data)  # Validate the data and email
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = randint(1000, 9999)  # Generate OTP
            # Checking if a user with OTP Exist
            is_exist = ForgetPasswordOTP.objects.filter(email=email).exists()
            if is_exist:
                otp_model = ForgetPasswordOTP.objects.get(email=email)
                otp_model.expire_time = timezone.now()
                otp_model.otp = otp  # If exist update the OTP
                otp_model.save()
            else:
                # If new user Create OTP Model
                ForgetPasswordOTP.objects.create(email=email, otp=otp)
                # initiate CELERY to send mail
            send_otp_mail_to_email.delay_on_commit(otp, email)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Forget password request",
                severity_level="info",
                description="User requested for forgot password request",
            )
            return Response({
                "status": "success",
                'code': status.HTTP_200_OK,
                'message': "OTP has been created successfully",
                "details": "OTP send successful"
            }, status=status.HTTP_200_OK)
        else:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="invalid request",
                severity_level="warning",
                description="User request was invalid due forgot password request",
            )
            return Response({
                "status": "failed",
                'code': status.HTTP_400_BAD_REQUEST,
                'message': "invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAuthenticated()]
        else:
            return [AllowAny()]

    def post(self, request):
        """
            Reset password for valid user with valid email address
        """
        try:
            data = request.data
            serializer = ResetPasswordSerializer(
                data=data)  # validate the request
            if serializer.is_valid():
                email = serializer.validated_data['email']
                password = serializer.validated_data['password']
                pass_change_token = serializer.validated_data['token']
                forget_password_otp_obj = get_object_or_404(
                    ForgetPasswordOTP, email=email)

                if pass_change_token != forget_password_otp_obj.token:
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="invalid request",
                        severity_level="warning",
                        description="User request was invalid because pass change_token and forgot password token didn't match",
                    )
                    return Response({
                        'code': status.HTTP_400_BAD_REQUEST,
                        'status': 'failed',
                        'message': "Error while matching token",
                        'detail': 'Token did not match',
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    try:
                        with transaction.atomic():
                            user = get_user_model().objects.get(email=email)
                            user.set_password(password)  # Change password
                            user.save()
                            # Create new token and return
                            refresh = RefreshToken.for_user(user)
                            access_token = refresh.access_token
                            forget_password_otp_obj.delete()
                            response = Response({
                                "status": "success",
                                "code": status.HTTP_200_OK,
                                "message": "Operation successful",
                                "access_token": str(access_token),
                                "refresh_token": str(refresh)
                            }, status=status.HTTP_200_OK)
                            # set cookie
                            response.set_cookie(
                                settings.SIMPLE_JWT["AUTH_COOKIE"],
                                str(access_token),
                                httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                                secure=env("COOKIE_SECURE") == "True",
                                max_age=timedelta(
                                    days=7).total_seconds()
                            )
                            response.set_cookie(
                                settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                                str(refresh),
                                httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                                secure=env("COOKIE_SECURE") == "True",
                                max_age=timedelta(
                                    days=7).total_seconds()
                            )
                            log_activity_task.delay_on_commit(
                                request_data_activity_log(request),
                                verb="Password reset",
                                severity_level="info",
                                description="password was reset successfully",
                            )
                            return response
                    except Exception as e:
                        logger.exception(str(e))
                        log_activity_task.delay_on_commit(
                            request_data_activity_log(request),
                            verb="Error occurred",
                            severity_level="warning",
                            description="Error occurred while resetting password",
                        )
                        return Response({
                            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "message": "Error occurred",
                            'status': 'failed', 'detail': str(e)
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Error occurred",
                    severity_level="warning",
                    description="Error occurred while resetting password",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    'status': "failed",
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error occurred",
                severity_level="warning",
                description="Error occurred while resetting password",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Something went wrong",
                'status': "failed",
                'errors': {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):

        user = request.user
        serializer = UpdatePasswordSerializer(
            data=request.data, context={"user": user})

        if serializer.is_valid():
            serializer.update(user, serializer.validated_data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Password change",
                severity_level="info",
                description="Password changed successfully",
            )
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Password Updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
        else:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Password change failed",
                severity_level="warning",
                description="Password changed failed because of validation error",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request data",
                "status": "failed",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class VerifyOtpView(APIView):
    def post(self, request):
        """
            Verify OTP with given email here
        """
        try:
            data = request.data
            serializer = VerifyOtpSerializer(data=data)
            if serializer.is_valid():
                email = serializer.validated_data["email"]
                otp = serializer.validated_data['otp']
                forget_password_otp_obj = get_object_or_404(
                    ForgetPasswordOTP, email=email)
                if forget_password_otp_obj.otp != otp:  # check if OTP matched
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="OTP verify failed",
                        severity_level="warning",
                        description="OTP verification failed",
                    )
                    return Response({
                        "code": status.HTTP_400_BAD_REQUEST,
                        "message": "Failed while verifying OTP",
                        "status": "failed",
                        "can_change_pass": False,
                        "details": "OTP didn't match"
                    }, status=status.HTTP_400_BAD_REQUEST)

                if forget_password_otp_obj.is_expired():  # check if OTP has expired
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="OTP verify failed",
                        severity_level="warning",
                        description="OTP verification failed because OTP has expired",
                    )
                    return Response({
                        "code": status.HTTP_400_BAD_REQUEST,
                        "message": "Failed while verifying OTP",
                        "status": "failed",
                        "can_change_pass": False,
                        "details": "OTP expired generate a new OTP"
                    }, status=status.HTTP_400_BAD_REQUEST)

                try:
                    token = generate_random_token()
                    forget_password_otp_obj.token = token
                    forget_password_otp_obj.save(update_fields=['token'])
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="OTP verify success",
                        severity_level="info",
                        description="OTP verification successfully done",
                    )
                    return Response({
                        "code": status.HTTP_200_OK,
                        "message": "Operation successful",
                        "status": "success",
                        "can_change_pass": True,
                        "details": "Generated new Token for changing password",
                        "token": token
                    }, status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(str(e))
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="OTP verify failed",
                        severity_level="warning",
                        description="OTP verification failed",
                    )
                    return Response({
                        "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": "Error occurred",
                        "status": "failed",
                        'errors': {'server_error': [str(e)]}

                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="OTP verify failed",
                    severity_level="warning",
                    description="OTP verification failed",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="OTP verify failed",
                severity_level="warning",
                description="OTP verification failed",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Something went wrong",
                'status': "failed",
                'errors': {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom refresh view to set the new refresh token in cookies
    """

    def post(self, request, *args, **kwargs):

        # Extract the refresh token from the request cookies
        refresh_token = request.COOKIES.get(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])

        if not refresh_token:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Error while getting refresh token",
                "errors": {
                    "refresh_token": ["No refresh token provided"]
                }}, status=status.HTTP_400_BAD_REQUEST)

        request.data.update({'refresh': refresh_token})
        # Proceed with refresh process (generates new access & refresh tokens)
        response = super().post(request, *args, **kwargs)

        # Handle error responses (e.g., invalid or expired token)
        if response.status_code == 400:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Refresh token generation failed",
                severity_level="warning",
                description="Response token generation failed",
            )
            return Response({
                "code": 400,
                "status": "failed",
                "message": response.data,
                "errors": {
                    "token": ["failed to get refresh token"]
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # If refresh token is generated, blacklist the old one
        if "refresh" in response.data:
            response.set_cookie(
                settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                response.data["refresh"],
                httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                secure=env("COOKIE_SECURE") == "True",
                max_age=timedelta(
                    days=15).total_seconds()
            )

        # Set the new access token in cookie
        if "access" in response.data:
            response.set_cookie(
                settings.SIMPLE_JWT["AUTH_COOKIE"],
                response.data['access'],
                httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                secure=env("COOKIE_SECURE") == "True",
                max_age=timedelta(
                    days=7).total_seconds()
            )

        # response.data.pop("access")
        # response.data.pop("refresh")
        response.data.update(
            {"code": 200, "status": "success", "message": "new access token given in cookie"})
        log_activity_task.delay_on_commit(
            request_data_activity_log(request),
            verb="Refresh token generation",
            severity_level="info",
            description="Response token generated successfully",
        )
        return response

    def handle_exception(self, exc):
        """
        Modify error messages for invalid/blacklisted tokens.
        """
        if isinstance(exc, InvalidToken):
            log_activity_task.delay_on_commit(
                request_data_activity_log(self.request),
                verb="Refresh token generation failed",
                severity_level="info",
                description="Response token generated successfully",
            )
            return Response({
                "code": 401,
                "status": "failed",
                "message": "invalid request",
                "errors": {
                    "token": ["Your refresh token is invalid or has been blacklisted."]
                }
            }, status=status.HTTP_401_UNAUTHORIZED)
        return super().handle_exception(exc)

# Authentication views

# User views


class UserView(APIView):
    permission_classes = [IsAuthenticated, ViewAllUserPermission]

    def get(self, request):
        try:
            data = get_user_model().objects.all().order_by("id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request, view=self)
            serializer = UserSerializer(paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Tried to view all users",
                severity_level="info",
                description="Viewed all users",
            )
            return paginator.get_paginated_response({
                'code': 200,
                'status': 'success',
                'message': "Viewing all available users",
                'data': serializer.data
            }, status=200)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while viewing all users",
                severity_level="error",
                description="Error while viewing all users",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomPermissionView(APIView):
    permission_classes = [IsAuthenticated, GroupPermissionManagement]

    def post(self, request):
        try:
            data = request.data
            serializer = CustomPermissionSerializer(data=data)

            if serializer.is_valid():
                permission = serializer.save()
                name = serializer.validated_data["name"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creating a custom permission",
                    severity_level="info",
                    description="Just created a custom permission",
                )
                return Response({
                    "code": status.HTTP_201_CREATED,
                    "message": "Operation successful",
                    "status": "success",
                    "data": {
                        "id": permission.id,
                        "permission_name": name
                    }
                }, status=status.HTTP_201_CREATED)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while creating a custom permission",
                severity_level="warning",
                description="Error occurred while creating a custom permission",
            )
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while creating a custom permission",
                severity_level="warning",
                description="Error occurred while creating a custom permission",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            all_permission = PermissonModel.objects.all()

            serializer = CustomPermissionSerializerForView(
                all_permission, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Getting all permissions",
                severity_level="info",
                description="Requested for viewing all permissions",
            )
            return Response(
                {
                    "code": status.HTTP_200_OK,
                    "message": "Operation successful",
                    "status": "success",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="error while getting all permissions",
                severity_level="warning",
                description="Requested for viewing all permissions but an error occurred",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupPermissionView(APIView):
    def get_permissions(self):

        if self.request.method == "POST":
            return [GroupPermissionManagement()]
        elif self.request.method == "GET":
            return [GroupPermissionManagement()]
        elif self.request.method == "DELETE":
            return [GroupPermissionManagement()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = GroupModelSerializer(
                data=data)
            if serializer.is_valid():
                group = serializer.save()
                permissions = group.permission.all()
                permission_ids = [perm.id for perm in permissions]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creating group",
                    severity_level="Info",
                    description="created a new group",
                )
                return Response({
                    "code": status.HTTP_201_CREATED,
                    "message": "Operation successfully",
                    "status": "success",
                    "group_id": group.id,
                    "name": group.name,
                    "permission": permission_ids
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creating group error",
                    severity_level="warning",
                    description="Bed request while creating a group",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "invalid request",
                    "status": "failed",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creating group error",
                severity_level="warning",
                description="error occurred while creating a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "invalid request",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:

            data = GroupModel.objects.all()
            serializer = GroupSerializerForViewAllGroups(data, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View all groups",
                severity_level="info",
                description="Made a request to view all the groups",
            )
            return Response({
                "code": status.HTTP_200_OK,
                "message": "operation successful",
                "status": "success",
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error viewing groups",
                severity_level="warning",
                description="Error occurred while viewing groups",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        data = request.data
        group = data.get('group')
        permission = data.get('permission')
        try:
            group_obj = GroupModel.objects.get(id=group)
            if group_obj:
                permission_exists = group_obj.permission.filter(
                    id=permission).exists()
                if permission_exists:
                    group_obj.permission.remove(permission)
                else:
                    return Response({
                        "code": status.HTTP_400_BAD_REQUEST,
                        "message": "Operation failed",
                        "status": "failed",
                        "data": {
                            "permission": ["Permission does not exist"]
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Deleting group",
                severity_level="info",
                description="Deleted a group",
            )
            clear_user_permissions_cache()
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Operation successful",
                "status": "success",
                "detail": "Permission deleted successfully"
            }, status=status.HTTP_200_OK)

        except GroupModel.DoesNotExist:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Operation failed",
                "status": "failed",
                "data": {
                    "group": ["Group does not exist"]
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while deleting group",
                severity_level="warning",
                description="Error occurred while deleting a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupPermissionViewV2(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [GroupPermissionManagement()]
        elif self.request.method == "GET":
            return [GroupPermissionManagement()]
        elif self.request.method == "DELETE":
            return [GroupPermissionManagement()]
        else:
            return [IsAuthenticated()]

    def get(self, request):
        try:
            data = GroupModel.objects.annotate(
                permission_count=Count('permission', distinct=True),
                user_count=Count("assigngrouppermission__id", distinct=True)
            )
            serializer = GroupSerializerForViewAllGroupsV2(data, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View all groups",
                severity_level="info",
                description="Made a request to view all the groups",
            )
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Fetched all available groups with permission count and user count.",
                "status": "success",
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error viewing groups",
                severity_level="warning",
                description="Error occurred while viewing groups",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpecificGroupPermissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ["DELETE", "PATCH"]:
            return [IsAuthenticated(), GroupPermissionManagement()]
        return [IsAuthenticated()]

    def patch(self, request, group_id):
        """Update a group with required permissions at least one permission"""
        try:
            group = get_object_or_404(GroupModel, pk=group_id)
            serializer = GroupModelSerializer(
                group, data=request.data)
            if serializer.is_valid():
                serializer.save()
                # after updating the group delete the permissions cache
                clear_user_permissions_cache()

                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Updated a group",
                    severity_level="info",
                    description="Updated a group with required permissions",
                )
                return Response({
                    "code": status.HTTP_200_OK,
                    "message": "Operation successful",
                    "status": "success",
                    'data': serializer.data
                })
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request in update group",
                    severity_level="warning",
                    description="Made a bad request for updating a group",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error",
                severity_level="info",
                description="Error while Updated a group with required permissions",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, group_id):
        """Delete a group"""
        print("DELETE view entered")

        try:
            group = get_object_or_404(GroupModel, pk=group_id)
            group.delete()
            # clear permissions cache for all users after a group deletion
            clear_user_permissions_cache()
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Deleted a group",
                severity_level="info",
                description="Deleted a group with required permissions",
            )
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Operation successful",
                "status": "success",
                'detail': f"Group deleted successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while deleting a group",
                severity_level="warning",
                description="Error occurred while deleting a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpecificGroupPermissionViewV2(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [GroupPermissionManagement()]
        elif self.request.method == "PATCH":
            return [GroupPermissionManagement()]
        else:
            return [IsAuthenticated()]

    def patch(self, request, group_id):
        """Update a group with required permissions at least one permission"""
        try:
            group = get_object_or_404(GroupModel, pk=group_id)
            serializer = GroupModelSerializerV2(
                group, data=request.data)
            if serializer.is_valid():
                serializer.save()
                # after updating the group delete the permissions cache
                clear_user_permissions_cache()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Updated a group",
                    severity_level="info",
                    description="Updated a group with required permissions",
                )
                return Response({
                    "code": status.HTTP_200_OK,
                    "message": "Operation successful",
                    "status": "success",
                    'data': serializer.data
                })
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request in update group",
                    severity_level="warning",
                    description="Made a bad request for updating a group",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error",
                severity_level="info",
                description="Error while Updated a group with required permissions",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignGroupPermissionView(APIView):
    permission_classes = [IsAuthenticated,
                          GroupPermissionManagement]

    def post(self, request):
        try:
            data = request.data
            serializer = AssignGroupPermissionSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                group = serializer.validated_data.get("group")
                user = serializer.validated_data.get("user")

                groups_data = []
                for gro in group:
                    groups_data.append(
                        {"group_id": gro.id, "group_name": gro.name})
                clear_user_permissions_cache()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Assigned a user to the group",
                    severity_level="info",
                    description="Assigned a user to the group with some permissions",
                )
                return Response({
                    "code": status.HTTP_201_CREATED,
                    "message": "Operation successful",
                    "status": "success",
                    "user_id": user.id,
                    "groups": groups_data
                }, status=status.HTTP_201_CREATED)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request in assign group",
                    severity_level="warning",
                    description="Bad request for Assigning a user to the group with some permissions",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error occurred assign group",
                severity_level="error",
                description="Error occurred while adding a user in a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {'server_error': [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        try:
            serializer = DeleteUserFromGroupSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data['user_id']
                group = serializer.validated_data['group_id']
                assign_group = AssignGroupPermission.objects.get(user=user)
                assign_group.group.remove(group)
                assign_group.save()
                clear_user_permissions_cache()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Deleted an user a group",
                    severity_level="info",
                    description="Made a request to delete an user from a group",
                )
                return Response({
                    "code": status.HTTP_200_OK,
                    "message": "Operation successful",
                    "status": "success",
                    "detail": "User removed from group successfully."
                }, status=status.HTTP_200_OK)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Error while deleting user from group",
                    severity_level="error",
                    description="Error occurred while deleting a user from a group",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while deleting user from group",
                severity_level="error",
                description="Error occurred while deleting a user from a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    "server_error": [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:

            data = AssignGroupPermission.objects.all()
            users_data = []
            for assign_group in data:
                user_info = {
                    "user_id": assign_group.user.id if assign_group.user else None,
                    "username": assign_group.user.username if assign_group.user else "No User",
                    "groups": []
                }
                for group in assign_group.group.all():
                    group_info = {
                        "group_id": group.id,
                        "group_name": group.name,
                        "permissions": [
                            {"permission_id": perm.id, "permission_name": perm.name}
                            for perm in group.permission.all()
                        ]
                    }
                    user_info["groups"].append(group_info)
                users_data.append(user_info)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Viewed all user with groups",
                severity_level="info",
                description="Made a request for viewing all user with their assigned groups",
            )
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Operation successful",
                "status": "success",
                "data": users_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error while viewing all users and their group",
                severity_level="error",
                description="Made a request for viewing all user with their assigned groups and an error occurred",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {
                    "server_error": [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            data = request.data
            user = data.get("user")
            group = data.get("group")
            if not user:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request while updating permission",
                    severity_level="error",
                    description="Made a request for updating user permission with their assigned groups and an error occurred",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": {
                        "user": ["user field must be needed"]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            if not group:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request while updating permission",
                    severity_level="error",
                    description="Made a request for updating user permission with their assigned groups and an error occurred",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": {
                        "group": ["Group is must need"]
                    }}, status=status.HTTP_400_BAD_REQUEST)

            instance = AssignGroupPermission.objects.get(user=user)
            serializer = AssignGroupPermissionSerializer(
                instance, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                user_id = serializer.validated_data["user"].id
                groups = serializer.validated_data["group"]
                groups_data = [{"group_id": gro.id,
                                "group_name": gro.name} for gro in groups]
                clear_user_permissions_cache()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="request for updating permission",
                    severity_level="info",
                    description="Made a request for updating user permission with their assigned groups",
                )
                return Response({
                    "code": status.HTTP_200_OK,
                    "message": "Operation successful",
                    "status": "success",
                    "user_id": user_id,
                    "updated_groups": groups_data
                }, status=status.HTTP_200_OK)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request while updating permission",
                    severity_level="error",
                    description="Made a request for updating user permission with their assigned groups and an error occurred",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        except AssignGroupPermission.DoesNotExist:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while updating permission",
                severity_level="error",
                description="Made a request for updating user permission with their assigned groups and an error occurred",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request",
                "status": "failed",
                "errors": {"user": ["User not found in AssignGroupPermission"]}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while updating permission",
                severity_level="error",
                description="Made a request for updating user permission with their assigned groups and an error occurred",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request",
                "status": "failed",
                "errors":
                {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_400_BAD_REQUEST)


class AssignGroupPermissionViewV2(APIView):
    permission_classes = [IsAuthenticated,
                          GroupPermissionManagement]

    def post(self, request):
        try:
            data = request.data
            serializer = AssignGroupPermissionSerializerV2(data=data)
            if serializer.is_valid():
                with transaction.atomic():
                    serializer.save()
                group = serializer.validated_data.get("group")
                users = serializer.validated_data.get("users")

                users_data = []
                for user in users:
                    users_data.append(
                        {"user_id": user.id, "username": user.username})
                clear_user_permissions_cache()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Assigned a user to the group",
                    severity_level="info",
                    description="Assigned a user to the group with some permissions",
                )
                return Response({
                    "code": status.HTTP_201_CREATED,
                    "message": "Operation successful",
                    "status": "success",
                    "users": users_data,
                    "group": group.id
                }, status=status.HTTP_201_CREATED)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Bad request in assign group",
                    severity_level="warning",
                    description="Bad request for Assigning a user to the group with some permissions",
                )
                return Response({
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid request",
                    "status": "failed",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error occurred assign group",
                severity_level="error",
                description="Error occurred while adding a user in a group",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {'server_error': [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminUserEmailView(APIView):
    permission_classes = [IsAuthenticated, RegisterUserPermission]

    def post(self, request):
        try:
            data = request.data
            serializer = AdminUserEmailSerializer(
                data=data)
            if serializer.is_valid():
                with transaction.atomic():
                    instance = serializer.save()
                    email = serializer.validated_data["email"]
                    try:
                        otp = OTP.objects.get(email=email)
                        otp_value = otp.otp
                        send_otp_email.delay_on_commit(email, otp_value)

                    except OTP.DoesNotExist:
                        log_activity_task.delay_on_commit(
                            request_data_activity_log(request),
                            verb="Bad request while registering user",
                            severity_level="warning",
                            description="Made a request for registering user and the request was invalid",
                        )
                        return Response({
                            "code": status.HTTP_404_NOT_FOUND,
                            "message": "Invalid request",
                            "status": "failed",
                            "errors": {
                                'otp': ["OTP for the provided email does not exist."]
                            }}, status=status.HTTP_404_NOT_FOUND)
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="Request for OTP sending",
                        severity_level="info",
                        description="Made a request for sending OTP",
                    )
                    response = Response({
                        "code": status.HTTP_201_CREATED,
                        "message": "Operation successful",
                        "status": "success",
                        "message": "OTP sent successfully",
                        "to": {
                            "email": email,
                        }
                    }, status=status.HTTP_201_CREATED)
                    # Add no cache header in response
                    response = add_no_cache_header_in_response(response)
                    return response
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while registering user",
                severity_level="warning",
                description="Made a request for registering user and the request was invalid",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request",
                "status": "failed",
                "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while registering user",
                severity_level="error",
                description="Made a request for registering user and the request got an error",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminUserVerifyOtpView(APIView):
    permission_classes = [IsAuthenticated, RegisterUserPermission]

    def post(self, request):
        try:
            data = request.data
            serializer = AdminUserVerifyOtpSerializer(
                data=data)
            if serializer.is_valid():
                email = serializer.validated_data["email"]
                otp = serializer.validated_data["otp"]
                otp_object = OTP.objects.get(email=email, otp=otp)
                otp_object.delete()
                try:
                    VerifySuccessfulEmail.objects.create(email=email)
                except Exception as e:
                    logger.exception(str(e))
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="Bad request while verifying user OTP",
                        severity_level="warning",
                        description="Made a request for verifying user OTP and request was invalid",
                    )
                    return Response({
                        "code": status.HTTP_400_BAD_REQUEST,
                        "message": "Invalid request",
                        "status": "failed",
                        "errors": {
                            'email': [str(e)]
                        }}, status=status.HTTP_400_BAD_REQUEST)

                response = Response({
                                    "code": status.HTTP_200_OK,
                                    "message": "Operation successful",
                                    "status": "success",
                                    "email": email,
                                    }, status=status.HTTP_200_OK)
                # Add no cache header in response
                response = add_no_cache_header_in_response(response)
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="OTP verified",
                    severity_level="info",
                    description="Made a request for verifying user OTP",
                )
                return response
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while verifying user OTP",
                severity_level="warning",
                description="Made a request for verifying user OTP and request was invalid",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request",
                "status": "failed",
                "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while verifying user OTP",
                severity_level="error",
                description="Made a request for verifying user OTP and request was invalid",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminUserRegistrationView(APIView):
    permission_classes = [IsAuthenticated, RegisterUserPermission]

    def post(self, request):
        try:
            data = request.data
            serializer = AdminUserRegistrationSerializer(
                data=data)
            if serializer.is_valid():
                user = serializer.save()
                username = serializer.validated_data["username"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Request for Registering an user",
                    severity_level="info",
                    description="Made a request for registering an user.",
                )
                return Response({
                    "code": status.HTTP_201_CREATED,
                    "message": "Operation successful",
                    "status": "success",
                    "username": username
                }, status=status.HTTP_201_CREATED)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while Registering an user",
                severity_level="warning",
                description="Made a request for registering an user and the request was invalid",
            )
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid request",
                "status": "failed",
                "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Bad request while Registering an user",
                severity_level="warning",
                description="Made a request for registering an user and the request was invalid",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            cache_key = f"specific_user_permissions::{user.id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                response = Response(cached_data, status=status.HTTP_200_OK)
                response = add_no_cache_header_in_response(response)
                response['X-Cache'] = 'HIT'
                return response

            data = AssignGroupPermission.objects.select_related(
                "user").prefetch_related("group", "group__permission").filter(user=user)
            users_data = []

            # resolve linked member (self-service) once
            member_profile = getattr(user, "member_profile", None)
            member_block = {
                "is_member": bool(member_profile) and not user.is_staff and not user.is_superuser,
                "member_id": member_profile.id if member_profile else None,
                "member_ID": member_profile.member_ID if member_profile else None,
                "member_name": (
                    f"{member_profile.first_name} {member_profile.last_name}".strip()
                    if member_profile else None),
            }

            for assign_group in data:
                user_info = {
                    "user_id": assign_group.user.id if assign_group.user else None,
                    "username": assign_group.user.username if assign_group.user else "No User",
                    "role": user.role,
                    "is_admin": user.is_superuser,
                    "is_staff": user.is_staff,
                    "must_change_password": user.must_change_password,
                    **member_block,
                    "groups": [],
                    "permissions": []
                }
                for group in assign_group.group.all():
                    group_info = {
                        "group_id": group.id,
                        "group_name": group.name,
                    }
                    user_info["groups"].append(group_info)
                    all_permissions = [{
                        "permission_id": perm.id, "permission_name": perm.name}
                        for perm in group.permission.all()]

                    user_info["permissions"].extend(all_permissions)
                users_data.append(user_info)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="retrieved user permissions",
                severity_level="info",
                description="retrieve permission get completed",
            )
            if not users_data:
                member_profile = getattr(user, "member_profile", None)
                user_info = {
                    "user_id":  user.id,
                    "username": user.username,
                    "role": user.role,
                    "is_admin": user.is_superuser,
                    "is_staff": user.is_staff,
                    "must_change_password": user.must_change_password,
                    "is_member": bool(member_profile) and not user.is_staff and not user.is_superuser,
                    "member_id": member_profile.id if member_profile else None,
                    "member_ID": member_profile.member_ID if member_profile else None,
                    "member_name": (
                        f"{member_profile.first_name} {member_profile.last_name}".strip()
                        if member_profile else None),
                    "groups": [],
                    "permissions": []
                }
                if user.role == "MEMBER":
                    member_group = GroupModel.objects.filter(name="club_member").prefetch_related("permission").first()
                    if member_group:
                        user_info["groups"].append({"group_id": member_group.id, "group_name": member_group.name})
                        user_info["permissions"] = [{"permission_id": perm.id, "permission_name": perm.name} for perm in member_group.permission.all()]
                users_data.append(user_info)

            response = Response({
                "code": status.HTTP_200_OK,
                "message": "Operation successful",
                "status": "success",
                "data": users_data},
                status=status.HTTP_200_OK)
            # add no cache header to response
            response = add_no_cache_header_in_response(response)
            cache.set(cache_key, response.data, 60)
            response['X-Cache'] = 'MISS'
            return response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error Occurred",
                severity_level="error",
                description="Error while getting user permissions",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Invalid request",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupDetailsView(APIView):
    permission_classes = [IsAuthenticated, GroupPermissionManagement]

    def get(self, request, id):
        try:
            group = GroupModel.objects.prefetch_related(
                "permission").get(id=id)
            permissions = group.permission.all()
            assign_group_permission_obj = AssignGroupPermission.objects.filter(
                group=group).select_related("user")
            users = [
                assign.user for assign in assign_group_permission_obj if assign.user]
            group_serializer = GroupDetailsSerializer(group)
            permission_serializer = CustomPermissionSerializerForView(
                permissions, many=True)
            user_serializer = UserSerializer(users, many=True)
            return Response({
                "code": 200,
                "status": "success",
                "data": {
                    "group": group_serializer.data,
                    "permissions": permission_serializer.data,
                    "users": user_serializer.data
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Error Occurred",
                severity_level="error",
                description="Error while getting all the groups",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Invalid request",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
