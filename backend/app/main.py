"""
نقطة الدخول الرئيسية.
هذا الملف مسؤوليته الوحيدة: تجميع (wire) كل شيء سوا — إنشاء التطبيق، تسجيل الـ Routers،
إعداد الـ Middleware. أي منطق فعلي ما لازم يكون هون.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import auth, users, categories, transactions, goals, personas, onboarding, agent

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API لتطبيق إدارة المال والتوفير مع وكيل الذكاء الاصطناعي رشيد",
    version="0.1.0",
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


@app.get("/health", tags=["System"])
def health_check():
    """Endpoint بسيط يستخدمه Docker/الخوادم للتأكد إن السيرفر شغال — معيار أساسي بأي نظام إنتاجي."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}
