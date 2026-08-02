from django.shortcuts import render
from django.http import JsonResponse



def health(request):
    return JsonResponse(
            {
                "status": "ok",
                "service": "curricula.live api",
            }
        )



# Create your views here.
