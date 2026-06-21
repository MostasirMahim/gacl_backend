from django.urls import path
from . import views
from . import order_views
urlpatterns = [
    path("v1/restaurants/", views.RestaurantView.as_view(),
         name="restaurant_view"),
    path("v1/restaurants/cusines/", views.RestaurantCuisineCategoryView.as_view(),
         name="restaurant_cuisine_view"),
    path("v1/restaurants/categories/", views.RestaurantCategoryView.as_view(),
         name="restaurant_categories_view"),
    path("v1/restaurants/items/categories/", views.RestaurantItemCategoryView.as_view(),
         name="restaurant_categories_view"),
    path("v1/restaurants/items/", views.RestaurantItemView.as_view(),
         name="restaurant_items_view"),
    path("v1/restaurants/items/media/", views.RestaurantItemMediaView.as_view(),
         name="restaurant_items_media_view"),
    path("v1/restaurants/items/buy/", views.RestaurantItemBuyView.as_view(),
         name="restaurant_items_buy_view"),
    path("v1/restaurants/upload/excel", views.RestaurantUploadExcelView.as_view(),
         name="restaurant_excel_file_upload"),

    # ---- Ordering / kitchen / billing ----
    path("v1/restaurants/spicy-levels/", order_views.SpicyLevelView.as_view(),
         name="restaurant_spicy_levels"),
    path("v1/restaurants/items/settings/", order_views.RestaurantItemSettingView.as_view(),
         name="restaurant_item_settings"),
    path("v1/restaurants/public-menu/", order_views.PublicMenuView.as_view(),
         name="restaurant_public_menu"),
    path("v1/restaurants/orders/", order_views.RestaurantOrderView.as_view(),
         name="restaurant_orders"),
    path("v1/restaurants/orders/<int:order_id>/verify-otp/",
         order_views.VerifyOrderOtpView.as_view(), name="restaurant_order_verify_otp"),
    path("v1/restaurants/kitchen/orders/", order_views.KitchenOrderView.as_view(),
         name="restaurant_kitchen_orders"),
    path("v1/restaurants/kitchen/orders/<int:order_id>/status/",
         order_views.KitchenOrderView.as_view(), name="restaurant_kitchen_order_status"),
    path("v1/restaurants/orders/<int:order_id>/bill/",
         order_views.BillOrderView.as_view(), name="restaurant_order_bill"),

    # ---- Inventory ----
    path("v1/restaurants/inventory/items/", order_views.RestaurantInventoryItemView.as_view(),
         name="restaurant_inventory_items"),
    path("v1/restaurants/inventory/movements/",
         order_views.RestaurantInventoryMovementView.as_view(),
         name="restaurant_inventory_movements"),
    path("v1/restaurants/items/recipes/", order_views.RestaurantItemRecipeView.as_view(),
         name="restaurant_item_recipes"),
]
