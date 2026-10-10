"""
إعداد الاتصال بقاعدة البيانات وإدارة الـ Sessions.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # يتحقق إن الاتصال حي قبل كل استخدام — يمنع أخطاء "connection closed"
    # الاستعلامات بتنطبع فقط لو SQL_ECHO مفعّل صراحة وبغير الإنتاج، ودايمًا بدون القيم (hide_parameters):
    # القيم فيها أرقام هواتف وهاشات كلمات مرور ونصوص رسائل بنكية وملاحظات مالية.
    echo=settings.SQL_ECHO and settings.ENVIRONMENT != "production",
    hide_parameters=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """الأساس المشترك لكل الـ Models."""
    pass


def get_db():
    """
    Dependency لـ FastAPI: يفتح Session جديدة لكل طلب ويغلقها تلقائيًا بعد الانتهاء،
    حتى لو حصل استثناء (Exception) — هذا يمنع تسريب الاتصالات (connection leaks).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
