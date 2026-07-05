from core.utils.pagination import CustomPageNumberPagination
from rest_framework.permissions import IsAdminUser
from activity_log.utils.permission_classes import AllUserActivityLogPermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import ActivityLog
from .utils.functions import log_request
from .serializers import AdminActivityLogSerializer, NormalUserActivityLogSerializer, AllUserActivityLogSerializer
import logging
from django.core.cache import cache
from django.utils.http import urlencode
logger = logging.getLogger("myapp")


class ActivityLogAPIView(APIView):
    """API View to fetch user activities."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            activity_logs = ActivityLog.objects.filter(
                user=user).exclude(request_method="GET").order_by('-id')

            if not activity_logs.exists():
                log_request(request, "No activity logs found for this user",
                            "info", "No activity logs found for this user")
                return Response({
                    "code": status.HTTP_200_OK,
                    "message": "No activity logs found for this user.",
                    "status": "failed",
                    "data": []
                }, status=status.HTTP_200_OK)
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"single_activity_logs::{query_string}_user_{user.id}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                activity_logs, request, view=self)

            if user.is_superuser:
                serializer = AdminActivityLogSerializer(
                    paginated_queryset, many=True)
            else:
                serializer = NormalUserActivityLogSerializer(
                    paginated_queryset, many=True)

            log_request(request, "retrieved logged data successfully",
                        "info", "retrieved logged data successfully")
            final_response = paginator.get_paginated_response({
                "code": status.HTTP_200_OK,
                "message": f"{user.username} retrieved logged data successfully",
                "status": "success",
                "data": serializer.data

            }, status=200)

            cache.set(cache_key, final_response.data, 60*10)
            return final_response

        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "An error occurred while retrieving activity logs",
                        "error", "An error occurred while retrieving activity logs")
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An error occurred while retrieving activity logs.",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AllUserActivityLogAPIView(APIView):
    """API View to fetch all user activities."""
    permission_classes = [IsAuthenticated, AllUserActivityLogPermission]

    def get(self, request):
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"all_activity_logs::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            activity_logs = ActivityLog.objects.all().order_by('-id')
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                activity_logs, request, view=self)
            serializer = AllUserActivityLogSerializer(
                paginated_queryset, many=True)

            final_response = paginator.get_paginated_response({
                "code": status.HTTP_200_OK,
                "message": "All user activity logs retrieved successfully",
                "status": "success",
                "data": serializer.data
            }, status=200)

            # cache.set(cache_key, final_response.data, 60*10)
            return final_response

        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An error occurred while retrieving all activity logs.",
                "status": "failed",
                "errors": {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
