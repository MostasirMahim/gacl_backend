from django.urls import path
from . import views

urlpatterns = [
    # Menu Sections management
    path('v1/restaurants/<int:restaurant_id>/sections/', views.RestaurantMenuSectionView.as_view(), name='restaurant_sections'),
    path('v1/restaurants/sections/<int:section_id>/', views.RestaurantMenuSectionDetailView.as_view(), name='restaurant_sections_detail'),
    
    # Testimonials management
    path('v1/restaurants/<int:restaurant_id>/testimonials/', views.RestaurantTestimonialView.as_view(), name='restaurant_testimonials'),
    path('v1/testimonials/<int:testimonial_id>/', views.RestaurantTestimonialDetailView.as_view(), name='restaurant_testimonials_detail'),

    # Reviews management
    path('v1/restaurants/<int:restaurant_id>/reviews/', views.RestaurantItemReviewListView.as_view(), name='restaurant_reviews'),
    path('v1/items/<int:item_id>/reviews/', views.ItemReviewCreateView.as_view(), name='item_reviews_create'),
    path('v1/reviews/<int:review_id>/', views.RestaurantItemReviewDetailView.as_view(), name='restaurant_reviews_detail'),

    # Item Media management
    path('v1/items/<int:item_id>/media/', views.RestaurantItemMediaCreateView.as_view(), name='item_media_create'),
    path('v1/media/<int:media_id>/', views.RestaurantItemMediaDeleteView.as_view(), name='item_media_delete'),
]
