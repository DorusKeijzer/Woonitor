from django.urls import path

from . import views

urlpatterns = [
    path("index/", views.index, name="index"), # lists all houses
    path("index", views.index, name="index"), # lists all houses
    path("", views.index, name="index"), # lists all houses

    path("<str:stad>/analyse/", views.analyse, name="analyse"),
    path("<str:stad>/analyse", views.analyse, name="analyse"),

    path("<str:stad>/<int:id>/", views.item, name="item"), # details on a specific house
    path("<str:stad>/<int:id>", views.item, name="item"), # details on a specific house

    path("<str:stad>/", views.stad, name="stad"), # landing page for a given city
    path("<str:stad>", views.stad, name="stad"), # landing page for a given city

]