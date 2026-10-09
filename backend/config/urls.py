from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.core.views import LivenessView, ReadinessView
from apps.ingestion import views as imports
from apps.portfolio import views as portfolio
from apps.users import views as auth

v1 = [
    path("health", ReadinessView.as_view(), name="health"),
    path("health/live", LivenessView.as_view(), name="health-live"),
    path("auth/login", auth.LoginView.as_view(), name="login"),
    path("auth/refresh", auth.RefreshView.as_view(), name="refresh"),
    path("auth/logout", auth.LogoutView.as_view(), name="logout"),
    path("auth/me", auth.MeView.as_view(), name="me"),
    path("customers", portfolio.CustomerListView.as_view(), name="customer-list"),
    path(
        "customers/<str:customer_id>",
        portfolio.CustomerDetailView.as_view(),
        name="customer-detail",
    ),
    path(
        "customers/<str:customer_id>/portfolio",
        portfolio.CustomerPortfolioView.as_view(),
        name="customer-portfolio",
    ),
    path(
        "customers/<str:customer_id>/transactions",
        portfolio.CustomerTransactionsView.as_view(),
        name="customer-transactions",
    ),
    path(
        "customers/<str:customer_id>/goals",
        portfolio.CustomerGoalsView.as_view(),
        name="customer-goals",
    ),
    path("goals/<str:goal_id>", portfolio.GoalDetailView.as_view(), name="goal-detail"),
    path("instruments", portfolio.InstrumentListView.as_view(), name="instrument-list"),
    path("admin/imports", imports.ImportBatchListView.as_view(), name="import-list"),
    path(
        "admin/imports/<int:batch_id>",
        imports.ImportBatchDetailView.as_view(),
        name="import-detail",
    ),
    path(
        "admin/imports/<int:batch_id>/rows",
        imports.ImportBatchRowsView.as_view(),
        name="import-rows",
    ),
    path("admin/imports/<str:dataset>", imports.ImportUploadView.as_view(), name="import-upload"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns = [path("api/v1/", include(v1))]
