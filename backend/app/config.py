"""
إعدادات التطبيق المركزية.
كل القيم القابلة للتغيير بين البيئات (dev/staging/prod) تُقرأ من متغيرات البيئة (.env)
ولا تُكتب مباشرة داخل الكود — هذا معيار أساسي لأي تطبيق جاهز للإنتاج والشراكة.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Rasheed - Finance Savings Agent"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql://rasheed_user:rasheed_pass@db:5432/rasheed_db"

    # --- Auth / JWT ---
    # ⚠️ عمدًا بدون قيمة افتراضية: كانت فيها قيمة ثابتة ("CHANGE_ME_IN_PRODUCTION")،
    # وبما إنه الريبو عام، أي حدا يقرأها من الكود مباشرة — فأي نشر ناسي يحدد
    # JWT_SECRET_KEY فعليًا بيوقع كل الـ Tokens بمفتاح معروف للعالم كامل.
    # هيك التطبيق يرفض يشتغل أصلًا بدون قيمة حقيقية بـ .env، بدل ما يشتغل
    # بصمت بمفتاح ضعيف معروف.
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24          # يوم واحد
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- AI Agent (رشيد) ---
    # --- AI Agent (رشيد) ---
    # ملاحظة: جوجل بتحدّث أسماء موديلات Gemini بوتيرة سريعة جدًا (كل بضعة أشهر)
    # وبتوقف موديلات قديمة فجأة. لو رشيد توقف يرد بالغلط، أول شي تتأكد منه
    # هو إذا اسم AGENT_MODEL لسا مدعوم عبر https://aistudio.google.com
    GEMINI_API_KEY: str = ""
    AGENT_MODEL: str = "gemini-3.6-flash"
    AGENT_DEFAULT_NAME: str = "رشيد"

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = ["*"]  # يُضيَّق في الإنتاج لدومين التطبيق فقط


@lru_cache
def get_settings() -> Settings:
    """
    استخدام lru_cache يضمن قراءة الإعدادات مرة واحدة فقط (Singleton)
    بدل إعادة قراءة .env في كل طلب — تحسين أداء بسيط لكنه معيار شائع.
    """
    return Settings()


settings = get_settings()
