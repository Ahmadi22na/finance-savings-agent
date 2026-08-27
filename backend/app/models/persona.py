"""
Persona كجدول قاعدة بيانات وليس Enum ثابت بالكود — قرار معماري مقصود:
"قابلة للزيادة حسب الترند" يعني إضافة شخصية رابعة لاحقًا لازم تكون Insert بقاعدة البيانات
(زي ما بنعمل بالتصنيفات)، مش Deploy لنسخة جديدة من الكود. نفس فلسفة Category بالضبط.
"""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class Persona(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "personas"

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # مثال: "wise", "business", "energetic"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)     # "رشيد الحكيم"
    tagline: Mapped[str] = mapped_column(String(200), nullable=False)          # جملة تعريفية قصيرة تظهر بشاشة الاختيار
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)          # "#1B4332"

    # نص التوجيه الأساسي لشخصية رشيد بهاي النسخة — يُستخدم كـ System Prompt عند التحدث لـ Gemini.
    # موجود بقاعدة البيانات (مش Hardcoded) عشان نقدر نضبط أسلوب الشخصية بدون Deploy جديد.
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # يسمح "نوقف" شخصية معينة بدون حذفها

    users: Mapped[list["User"]] = relationship(back_populates="persona")
