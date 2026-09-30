from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 100    
    page_size_query_param = 'page_size' 
    max_page_size = 500

    def get_paginated_response(self, data,status=200):
        return Response({
            **({"data": data} if isinstance(data, list) else data),
            "pagination": {
                    "count": self.page.paginator.count,
                    "total_pages": self.page.paginator.num_pages,
                    "current_page": self.page.number,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "page_size": self.page_size,
                }
            
            
        },status=status)