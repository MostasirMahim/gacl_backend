import datetime
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from restaurant.models import (
    Restaurant,
    RestaurantCategory,
    RestaurantCuisineCategory,
    RestaurantItemCategory,
    RestaurantMenuSection,
    RestaurantItem,
    RestaurantTestimonial,
    RestaurantItemReview
)

class Command(BaseCommand):
    help = 'Seeds database with default premium Restan restaurant, menu sections, items, and reviews.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting restaurant database seeding..."))

        # 1. Create categories
        cuisine_type, _ = RestaurantCuisineCategory.objects.get_or_create(name="Multicuisine")
        restaurant_type, _ = RestaurantCategory.objects.get_or_create(name="Fine Dining")

        # 2. Get or Create the Restaurant (to avoid ProtectedError with Invoices)
        restaurant = Restaurant.objects.filter(slug="restan").first()
        if not restaurant:
            restaurant = Restaurant.objects.filter(slug="burger-house").first()

        defaults = {
            "name": "Restan",
            "slug": "restan",
            "description": "Experience gourmet breakfast, fine desserts, premium seafood, and fresh beverages prepared by world-class chefs in a cozy, modern atmosphere.",
            "address": "175 10h Street, Office 375 Berlin, De 21562",
            "city": "Berlin",
            "state": "Berlin",
            "postal_code": "21562",
            "phone": "+123 34598768",
            "operating_hours": 12,
            "capacity": 120,
            "status": "open",
            "opening_time": datetime.time(8, 0),
            "closing_time": datetime.time(22, 0),
            "booking_fees_per_seat": 10.00,
            "cuisine_type": cuisine_type,
            "restaurant_type": restaurant_type,
            "banner_bg_image": "https://images.unsplash.com/photo-1497534446932-c925b458314e?w=1600&q=80",
            "banner_title": "Restan Food Menu",
            "banner_description": "Savor our collection of gourmet dishes, sweet bakery delights, fresh catches from the ocean, and artisan beverages crafted to perfection.",
            "about_text": "Founded in 2018, Restan brings a refined twist to casual classic dining. We source our ingredients from certified local organic farms, and our secrets are prepared fresh daily by world-class chefs.",
            "meta_title": "Restan - Premium Food Menu & Dining",
            "meta_description": "Indulge in high-quality gourmet breakfast, lunches, sea food, and premium beverages at Restan.",
            "delivery_banner_title": "30 Minutes Delivery!",
            "delivery_banner_text": "A relaxing and pleasant atmosphere, good jazz, dinner, and cocktails. The Patio Time Bar opens in the center of Florence. The only bar inspired by the 1960s, it will give you a experience that you’ll have a hard time forgetting.",
            "reservation_banner_title": "Reservation Your Favorite Private Table",
            "reservation_banner_text": "A relaxing and pleasant atmosphere, good jazz, dinner, and cocktails. The Patio Time Bar opens in the center of Florence. The only bar inspired by the 1960s, it will give you a experience that you’ll have a hard time forgetting.",
            "reservation_banner_launch_menu": "30+ items",
            "reservation_banner_dinner_menu": "50+ items",
            "footer_config": {
                "about_us": {
                    "text": "Continued at zealously necessary is Surrounded sir motionless she end literature. Gay direction neglected.",
                    "facebook": "https://facebook.com",
                    "twitter": "https://twitter.com",
                    "youtube": "https://youtube.com",
                    "linkedin": "https://linkedin.com"
                },
                "contact_info": {
                    "address": "175 10h Street, Office 375 Berlin, De 21562",
                    "phone_1": "+123 34598768",
                    "phone_2": "+554 34598734",
                    "email": "food@restan.com"
                },
                "newsletter": {
                    "text": "Join our subscribers list to get the latest news and special offers."
                },
                "explore": [
                    { "label": "Menu", "link": "/resturent/food-menu" },
                    { "label": "About", "link": "#" },
                    { "label": "Help Center", "link": "#" },
                    { "label": "Career", "link": "#" },
                    { "label": "Features", "link": "#" },
                    { "label": "Contact", "link": "#" }
                ]
            }
        }

        if restaurant:
            for key, val in defaults.items():
                setattr(restaurant, key, val)
            restaurant.save()
            self.stdout.write(self.style.SUCCESS(f"Updated Restaurant: {restaurant.name} (ID: {restaurant.id})"))
        else:
            restaurant = Restaurant.objects.create(**defaults)
            self.stdout.write(self.style.SUCCESS(f"Created Restaurant: {restaurant.name} (ID: {restaurant.id})"))

        # 3. Define Menu Sections
        sections_data = [
            {
                "title": "Breakfast",
                "order": 1,
                "description": "Breakfast Specials",
                "layout_type": "default",
                "cover_image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800&q=80"
            },
            {
                "title": "Lunch",
                "order": 2,
                "description": "Lunch Specials",
                "layout_type": "default",
                "cover_image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800&q=80"
            },
            {
                "title": "Sea Food",
                "order": 3,
                "description": "Fresh from ocean",
                "layout_type": "left",
                "cover_image": "https://images.unsplash.com/photo-1551248429-40975aa4de74?w=800&q=80"
            },
            {
                "title": "Beverage",
                "order": 4,
                "description": "Drinks & Wine",
                "layout_type": "right",
                "cover_image": "https://images.unsplash.com/photo-1497534446932-c925b458314e?w=800&q=80"
            }
        ]

        sections = {}
        new_section_titles = [sec["title"] for sec in sections_data]
        for sec in sections_data:
            section, created = RestaurantMenuSection.objects.update_or_create(
                restaurant=restaurant,
                title=sec["title"],
                defaults={
                    "description": sec["description"],
                    "order": sec["order"],
                    "layout_type": sec["layout_type"],
                    "cover_image": sec["cover_image"],
                    "is_active": True
                }
            )
            sections[sec["title"]] = section
            status_str = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {status_str} Menu Section: {section.title} ({section.layout_type})"))

        # Deactivate any old sections not in the new list
        for old_sec in RestaurantMenuSection.objects.filter(restaurant=restaurant).exclude(title__in=new_section_titles):
            old_sec.is_active = False
            old_sec.save()
            self.stdout.write(self.style.WARNING(f"  Deactivated old Menu Section: {old_sec.title}"))

        # 4. Create Item Categories
        item_categories = {}
        for cat_name in ["Breakfast", "Lunch", "Seafood", "Beverages", "Desserts"]:
            cat, _ = RestaurantItemCategory.objects.get_or_create(name=cat_name)
            item_categories[cat_name] = cat

        # 5. Define Menu Items
        items_data = [
            # Breakfast (layout_type='default')
            {
                "name": "Chicken Alfredo",
                "description": "Creamy fettuccine Alfredo tossed with succulent grilled chicken breast, fresh parmesan, and cracked black pepper.",
                "unit": "plate",
                "unit_cost": 8.00,
                "selling_price": 40.00,
                "half_price": 20.00,
                "category": item_categories["Breakfast"],
                "menu_section": sections["Breakfast"],
                "stock": 50,
                "free_bonus": "Free Drinks",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Alfredo", "Pasta", "Best Seller"],
                "sku": "RES-BF-01",
                "cover_image": "https://images.unsplash.com/photo-1645112411341-6c4fd023714a?w=500&q=80"
            },
            {
                "name": "Fish Chips",
                "description": "Crispy beer-battered Atlantic cod served with thick-cut golden chips, fresh house salad, and tangy tartare sauce.",
                "unit": "plate",
                "unit_cost": 10.00,
                "selling_price": 70.00,
                "half_price": 36.00,
                "category": item_categories["Breakfast"],
                "menu_section": sections["Breakfast"],
                "stock": 40,
                "free_bonus": "Free Drinks",
                "sub_items": "Atlantic / chips / salad / tartare",
                "tags": ["Fish", "Chips", "Traditional"],
                "sku": "RES-BF-02",
                "cover_image": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=500&q=80"
            },
            {
                "name": "Ebony Fillet Steak",
                "description": "Prime-aged black angus beef fillet steak cooked to perfection, served with velvety truffle mash and green pepper sauce.",
                "unit": "plate",
                "unit_cost": 15.00,
                "selling_price": 85.00,
                "half_price": 44.00,
                "category": item_categories["Breakfast"],
                "menu_section": sections["Breakfast"],
                "stock": 30,
                "free_bonus": "Free Drinks",
                "sub_items": "Truffle mash / pepper sauce",
                "tags": ["Steak", "Beef", "Chef Special"],
                "sku": "RES-BF-03",
                "cover_image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=500&q=80"
            },
            {
                "name": "Chicken Grill",
                "description": "Tender flame-grilled chicken breast seasoned with herbs, served with roasted vegetables and wild rice.",
                "unit": "plate",
                "unit_cost": 8.00,
                "selling_price": 40.00,
                "half_price": 20.00,
                "category": item_categories["Breakfast"],
                "menu_section": sections["Breakfast"],
                "stock": 50,
                "free_bonus": "Free Drinks",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Grill", "Chicken", "Healthy"],
                "sku": "RES-BF-04",
                "cover_image": "https://images.unsplash.com/photo-1598515214211-89d3e73ae83b?w=500&q=80"
            },

            # Lunch (layout_type='default')
            {
                "name": "Cupcakes",
                "description": "Assorted freshly baked cupcakes with rich buttercream frosting, decorated with sprinkles.",
                "unit": "4 pcs",
                "unit_cost": 4.00,
                "selling_price": 20.00,
                "half_price": 10.00,
                "category": item_categories["Desserts"],
                "menu_section": sections["Lunch"],
                "stock": 60,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Sweet", "Cake", "Kids Favorite"],
                "sku": "RES-LH-01",
                "cover_image": "https://images.unsplash.com/photo-1587314168485-3236d6710814?w=500&q=80"
            },
            {
                "name": "Brownies",
                "description": "Fudgy chocolate brownies made with premium cocoa and loaded with dark chocolate chunks.",
                "unit": "4 pcs",
                "unit_cost": 3.00,
                "selling_price": 30.00,
                "half_price": 16.00,
                "category": item_categories["Desserts"],
                "menu_section": sections["Lunch"],
                "stock": 50,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Atlantic / chips / salad / tartare",
                "tags": ["Chocolate", "Fudgy", "Sweet"],
                "sku": "RES-LH-02",
                "cover_image": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=500&q=80"
            },
            {
                "name": "Muffins",
                "description": "Soft and fluffy muffins packed with wild blueberries and a hint of fresh lemon zest.",
                "unit": "4 pcs",
                "unit_cost": 4.00,
                "selling_price": 40.00,
                "half_price": 22.00,
                "category": item_categories["Desserts"],
                "menu_section": sections["Lunch"],
                "stock": 45,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Truffle mash / pepper sauce",
                "tags": ["Muffin", "Berry", "Breakfast"],
                "sku": "RES-LH-03",
                "cover_image": "https://images.unsplash.com/photo-1607958996333-41aef7caefaa?w=500&q=80"
            },
            {
                "name": "Cheesecakes",
                "description": "Creamy classic New York cheesecake slices on a buttery graham cracker crust with strawberry glaze.",
                "unit": "2 slices",
                "unit_cost": 6.00,
                "selling_price": 65.00,
                "half_price": 34.00,
                "category": item_categories["Desserts"],
                "menu_section": sections["Lunch"],
                "stock": 30,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Cheese", "Berry", "Sweet"],
                "sku": "RES-LH-04",
                "cover_image": "https://images.unsplash.com/photo-1524351199679-46cddf530c04?w=500&q=80"
            },

            # Sea Food (layout_type='left')
            {
                "name": "Salmon Fry",
                "description": "Pan-seared Atlantic salmon fillet with crispy skin, served with garlic herb butter and seasonal greens.",
                "unit": "plate",
                "unit_cost": 12.00,
                "selling_price": 80.00,
                "half_price": 40.00,
                "category": item_categories["Seafood"],
                "menu_section": sections["Sea Food"],
                "stock": 35,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Salmon", "Fish", "Healthy"],
                "sku": "RES-SF-01",
                "cover_image": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=500&q=80"
            },
            {
                "name": "Pangasius or Basa",
                "description": "Delicate grilled basa fillet seasoned with mild spices, served with fresh lemon-herb rice.",
                "unit": "plate",
                "unit_cost": 5.00,
                "selling_price": 30.00,
                "half_price": 15.00,
                "category": item_categories["Seafood"],
                "menu_section": sections["Sea Food"],
                "stock": 60,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Atlantic / chips / salad / tartare",
                "tags": ["Basa", "Fish", "Grilled"],
                "sku": "RES-SF-02",
                "cover_image": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=500&q=80"
            },
            {
                "name": "Clams",
                "description": "Freshly steamed littleneck clams in a rich white wine, garlic, and butter broth, served with crusty bread.",
                "unit": "plate",
                "unit_cost": 8.00,
                "selling_price": 90.00,
                "half_price": 45.00,
                "category": item_categories["Seafood"],
                "menu_section": sections["Sea Food"],
                "stock": 40,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Truffle mash / pepper sauce",
                "tags": ["Clams", "Shellfish", "Wine Broth"],
                "sku": "RES-SF-03",
                "cover_image": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=500&q=80"
            },
            {
                "name": "Red Crab",
                "description": "Succulent red crab legs steamed to perfection, served with warm drawn butter and lemon wedges.",
                "unit": "plate",
                "unit_cost": 10.00,
                "selling_price": 40.00,
                "half_price": 20.00,
                "category": item_categories["Seafood"],
                "menu_section": sections["Sea Food"],
                "stock": 25,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Crab", "Seafood", "Premium"],
                "sku": "RES-SF-04",
                "cover_image": "https://images.unsplash.com/photo-1553618551-fba689030290?w=500&q=80"
            },

            # Beverage (layout_type='right')
            {
                "name": "Wine",
                "description": "A glass of premium vintage red wine with rich oaky undertones and a smooth finish.",
                "unit": "glass",
                "unit_cost": 6.00,
                "selling_price": 65.00,
                "half_price": 34.00,
                "category": item_categories["Beverages"],
                "menu_section": sections["Beverage"],
                "stock": 100,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Wine", "Red Wine", "Alcohol"],
                "sku": "RES-BV-01",
                "cover_image": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=500&q=80"
            },
            {
                "name": "Coffee",
                "description": "Freshly brewed organic dark roast espresso coffee made from hand-picked Arabica beans.",
                "unit": "cup",
                "unit_cost": 1.50,
                "selling_price": 90.00,
                "half_price": 45.00,
                "category": item_categories["Beverages"],
                "menu_section": sections["Beverage"],
                "stock": 150,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Atlantic / chips / salad / tartare",
                "tags": ["Coffee", "Hot", "Caffeine"],
                "sku": "RES-BV-02",
                "cover_image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=500&q=80"
            },
            {
                "name": "Hot chocolate",
                "description": "Velvety, rich hot chocolate made with melted Belgian dark chocolate, topped with marshmallows.",
                "unit": "cup",
                "unit_cost": 2.00,
                "selling_price": 85.00,
                "half_price": 44.00,
                "category": item_categories["Beverages"],
                "menu_section": sections["Beverage"],
                "stock": 80,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Truffle mash / pepper sauce",
                "tags": ["Chocolate", "Sweet", "Hot Drink"],
                "sku": "RES-BV-03",
                "cover_image": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=500&q=80"
            },
            {
                "name": "Milk Shake",
                "description": "Thick and creamy classic vanilla bean milkshake blended with fresh organic milk and topped with whipped cream.",
                "unit": "glass",
                "unit_cost": 2.00,
                "selling_price": 40.00,
                "half_price": 20.00,
                "category": item_categories["Beverages"],
                "menu_section": sections["Beverage"],
                "stock": 90,
                "free_bonus": "Extra Free Juice",
                "sub_items": "Ricotta / goat cheese / beetroot",
                "tags": ["Shake", "Cold", "Sweet"],
                "sku": "RES-BV-04",
                "cover_image": "https://images.unsplash.com/photo-1579954115545-a95591f28bfc?w=500&q=80"
            }
        ]

        created_items = []
        new_item_names = [item_info["name"] for item_info in items_data]
        for item_info in items_data:
            item, created = RestaurantItem.objects.update_or_create(
                restaurant=restaurant,
                name=item_info["name"],
                defaults={
                    "slug": slugify(item_info["name"]),
                    "description": item_info["description"],
                    "unit": item_info["unit"],
                    "unit_cost": item_info["unit_cost"],
                    "selling_price": item_info["selling_price"],
                    "half_price": item_info.get("half_price"),
                    "category": item_info["category"],
                    "menu_section": item_info["menu_section"],
                    "stock": item_info["stock"],
                    "free_bonus": item_info.get("free_bonus", ""),
                    "sub_items": item_info.get("sub_items", ""),
                    "tags": item_info.get("tags", []),
                    "sku": item_info["sku"],
                    "cover_image": item_info["cover_image"],
                    "is_active": True
                }
            )
            created_items.append(item)
            status_str = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"    {status_str} Menu Item: {item.name}"))

        # Deactivate any old items not in the new list
        for old_item in RestaurantItem.objects.filter(restaurant=restaurant).exclude(name__in=new_item_names):
            old_item.is_active = False
            old_item.save()
            self.stdout.write(self.style.WARNING(f"    Deactivated old Menu Item: {old_item.name}"))

        # 6. Create Restaurant Testimonials
        # Delete existing testimonials since they are not protected by FKs and recreate
        RestaurantTestimonial.objects.filter(restaurant=restaurant).delete()
        testimonials_data = [
            {
                "name": "Matthew J. Wyman",
                "designation": "Senior Consultant",
                "rating": 5,
                "title": "Amazing culinary experience",
                "text": "The Chicken Alfredo is absolutely spectacular. The ingredients were incredibly fresh and the taste was authentic and delicious. Clean, premium environment and friendly staff."
            },
            {
                "name": "Istiak Ahmed",
                "designation": "Marketing Manager",
                "rating": 5,
                "title": "Awesome and delicious food",
                "text": "Highly recommend the Salmon Fry and the classic Cheesecakes! Restan has completely redefined upscale casual dining for me. Will be ordering regularly."
            }
        ]

        for test in testimonials_data:
            testimonial = RestaurantTestimonial.objects.create(
                restaurant=restaurant,
                name=test["name"],
                designation=test["designation"],
                rating=test["rating"],
                title=test["title"],
                text=test["text"]
            )
            self.stdout.write(self.style.SUCCESS(f"  Created Testimonial from: {testimonial.name}"))

        # 7. Create Item Reviews
        # Delete existing reviews for this restaurant's items and recreate
        RestaurantItemReview.objects.filter(item__restaurant=restaurant).delete()
        item_reviews_data = {
            "Chicken Alfredo": [
                {
                    "reviewer_name": "Sarah Jenkins",
                    "rating": 5,
                    "review_text": "An absolute masterpiece. Creamy Alfredo sauce is perfect. Must try!"
                },
                {
                    "reviewer_name": "David Miller",
                    "rating": 4,
                    "review_text": "Very delicious and satisfying. The chicken was cooked perfectly."
                }
            ],
            "Salmon Fry": [
                {
                    "reviewer_name": "Emily Watson",
                    "rating": 5,
                    "review_text": "The crispy skin and garlic herb butter are wonderful! Best salmon in the city!"
                }
            ]
        }

        for item in created_items:
            reviews = item_reviews_data.get(item.name, [
                {
                    "reviewer_name": "John Doe",
                    "rating": 5,
                    "review_text": f"Excellent quality and fantastic taste. The {item.name} is a stellar choice."
                }
            ])
            for rev in reviews:
                review = RestaurantItemReview.objects.create(
                    item=item,
                    reviewer_name=rev["reviewer_name"],
                    rating=rev["rating"],
                    review_text=rev["review_text"]
                )
                self.stdout.write(self.style.SUCCESS(f"    Created Review for {item.name} by {review.reviewer_name}"))

        self.stdout.write(self.style.SUCCESS("Restaurant database seeding completed successfully!"))
