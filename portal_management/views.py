from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import logging

from restaurant.models import Restaurant, RestaurantMenuSection, RestaurantTestimonial, RestaurantItemReview, RestaurantItem
from restaurant.utils.permission_classes import RestaurantManagementPermission
from . import serializers
from member.models import Member

logger = logging.getLogger("myapp")


class RestaurantMenuSectionView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def get(self, request, restaurant_id):
        try:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
            sections = RestaurantMenuSection.objects.filter(restaurant=restaurant, is_active=True).order_by("order")
            serializer = serializers.RestaurantMenuSectionSerializer(sections, many=True)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Sections fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, restaurant_id):
        try:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
            serializer = serializers.RestaurantMenuSectionSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(restaurant=restaurant)
                # Invalidate public restaurant cache
                cache.delete_pattern("restaurant_public_menu::*")
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Section created successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantMenuSectionDetailView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def patch(self, request, section_id):
        try:
            section = get_object_or_404(RestaurantMenuSection, id=section_id, is_active=True)
            serializer = serializers.RestaurantMenuSectionSerializer(section, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                cache.delete_pattern("restaurant_public_menu::*")
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Section updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, section_id):
        try:
            section = get_object_or_404(RestaurantMenuSection, id=section_id, is_active=True)
            section.is_active = False
            section.save()
            cache.delete_pattern("restaurant_public_menu::*")
            return Response({
                "code": 200,
                "status": "success",
                "message": "Section deleted successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantTestimonialView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def get(self, request, restaurant_id):
        try:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
            testimonials = RestaurantTestimonial.objects.filter(restaurant=restaurant, is_active=True).order_by("-id")
            serializer = serializers.RestaurantTestimonialSerializer(testimonials, many=True)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Testimonials fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, restaurant_id):
        try:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
            serializer = serializers.RestaurantTestimonialSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(restaurant=restaurant)
                cache.delete_pattern("restaurant_public_menu::*")
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Testimonial created successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantTestimonialDetailView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def patch(self, request, testimonial_id):
        try:
            testimonial = get_object_or_404(RestaurantTestimonial, id=testimonial_id, is_active=True)
            serializer = serializers.RestaurantTestimonialSerializer(testimonial, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                cache.delete_pattern("restaurant_public_menu::*")
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Testimonial updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, testimonial_id):
        try:
            testimonial = get_object_or_404(RestaurantTestimonial, id=testimonial_id, is_active=True)
            testimonial.is_active = False
            testimonial.save()
            cache.delete_pattern("restaurant_public_menu::*")
            return Response({
                "code": 200,
                "status": "success",
                "message": "Testimonial deleted successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemReviewListView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def get(self, request, restaurant_id):
        try:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
            reviews = RestaurantItemReview.objects.filter(item__restaurant=restaurant, is_active=True).order_by("-id")
            serializer = serializers.RestaurantItemReviewSerializer(reviews, many=True)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Reviews fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItemReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id):
        try:
            item = get_object_or_404(RestaurantItem, id=item_id, is_active=True)
            # Find the member associated with the logged-in user
            member = get_object_or_404(Member, user=request.user)
            
            serializer = serializers.RestaurantItemReviewSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(item=item, member=member)
                try:
                    cache.delete_pattern("restaurant_public_menu::*")
                except Exception:
                    pass
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Review submitted successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemReviewDetailView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def patch(self, request, review_id):
        try:
            review = get_object_or_404(RestaurantItemReview, id=review_id, is_active=True)
            serializer = serializers.RestaurantItemReviewSerializer(review, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                try:
                    cache.delete_pattern("restaurant_public_menu::*")
                except Exception:
                    pass
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Review updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Bad request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, review_id):
        try:
            review = get_object_or_404(RestaurantItemReview, id=review_id, is_active=True)
            review.is_active = False
            review.save()
            try:
                cache.delete_pattern("restaurant_public_menu::*")
            except Exception:
                pass
            return Response({
                "code": 200,
                "status": "success",
                "message": "Review deleted successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework import parsers
from restaurant.models import RestaurantItemMedia

class RestaurantItemMediaCreateView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, item_id):
        try:
            item = RestaurantItem.objects.get(id=item_id, is_active=True)
            image_file = request.FILES.get("image")
            if not image_file:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "No image file provided"
                }, status=status.HTTP_400_BAD_REQUEST)

            media = RestaurantItemMedia.objects.create(
                item=item,
                image=image_file
            )

            try:
                cache.delete_pattern("restaurant_public_menu::*")
                cache.delete_pattern("restaurant_items::*")
            except Exception:
                pass

            return Response({
                "code": 201,
                "status": "success",
                "message": "Item media image uploaded successfully",
                "data": {
                    "id": media.id,
                    "image": media.image.url
                }
            }, status=status.HTTP_201_CREATED)

        except RestaurantItem.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Item not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Failed to upload image",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemMediaDeleteView(APIView):
    permission_classes = [IsAuthenticated, RestaurantManagementPermission]

    def delete(self, request, media_id):
        try:
            media = RestaurantItemMedia.objects.get(id=media_id)
            media.delete()
            
            try:
                cache.delete_pattern("restaurant_public_menu::*")
                cache.delete_pattern("restaurant_items::*")
            except Exception:
                pass

            return Response({
                "code": 200,
                "status": "success",
                "message": "Item media image deleted successfully"
            }, status=status.HTTP_200_OK)
        except RestaurantItemMedia.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Media image not found"
            }, status=status.HTTP_404_NOT_FOUND)

