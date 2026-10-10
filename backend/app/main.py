"""
نقطة الدخول الرئيسية.
هذا الملف مسؤوليته الوحيدة: تجميع (wire) كل شيء سوا — إنشاء التطبيق، تسجيل الـ Routers،
إعداد الـ Middleware. أي منطق فعلي ما لازم يكون هون.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.docs import APP_DESCRIPTION, TAGS_METADATA
from app.api.routes import auth, users, categories, transactions, goals, personas, onboarding, agent

app = FastAPI(
    title=settings.APP_NAME,
    description=APP_DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    swagger_ui_parameters={
        "persistAuthorization": True,  # يحفظ التوكن بين تحديثات الصفحة
        "displayRequestDuration": True,
        "docExpansion": "list",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(personas.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")


@app.get(
    "/health",
    tags=["System"],
    summary="فحص حالة السيرفر",
    description="يرجّع حالة السيرفر واسم التطبيق والبيئة. بدون مصادقة؛ يستخدمه Docker والخوادم للتأكد إن الخدمة شغّالة.",
)
def health_check():
    """Endpoint بسيط يستخدمه Docker/الخوادم للتأكد إن السيرفر شغال — معيار أساسي بأي نظام إنتاجي."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}
