"""seed default categories

Revision ID: ddec2359eacc
Revises: fd931a6d75d4
Create Date: 2026-08-25 10:41:25.610252

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'ddec2359eacc'
down_revision: Union[str, None] = 'fd931a6d75d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# جدول مؤقت (metadata فقط) للتعامل مع بيانات categories بدون الاعتماد على الـ ORM Model،
# لأن الـ Model ممكن يتغيّر مستقبلاً بينما هالـ migration لازم يضل يشتغل بنفس الشكل دايمًا.
categories_table = sa.table(
    "categories",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("icon", sa.String),
    sa.column("is_default", sa.Boolean),
    sa.column("category_type", sa.String),
    sa.column("keywords", sa.JSON),
    sa.column("user_id", UUID(as_uuid=True)),
)

DEFAULT_CATEGORIES = [
    {"name": "مطاعم وكافيهات", "icon": "utensils", "type": "EXPENSE",
     "keywords": ["مطعم", "أكل", "برجر", "بيتزا", "كافيه", "قهوة", "مقهى", "فطور", "غدا", "عشا"]},
    {"name": "مواصلات", "icon": "car", "type": "EXPENSE",
     "keywords": ["بنزين", "تكسي", "أوبر", "كريم", "باص", "سرفيس", "مواصلات", "سيارة"]},
    {"name": "بقالة وسوبرماركت", "icon": "shopping-cart", "type": "EXPENSE",
     "keywords": ["بقالة", "سوبرماركت", "كارفور", "سفوي", "خضار", "فواكه", "تسوق بيت"]},
    {"name": "فواتير واشتراكات", "icon": "receipt", "type": "EXPENSE",
     "keywords": ["فاتورة", "كهرباء", "مي", "انترنت", "اشتراك", "نتفلكس", "موبايل", "خط"]},
    {"name": "تسوق", "icon": "shopping-bag", "type": "EXPENSE",
     "keywords": ["تسوق", "لبس", "شراء", "مول", "حذا", "ملابس"]},
    {"name": "صحة", "icon": "heart-pulse", "type": "EXPENSE",
     "keywords": ["دكتور", "صيدلية", "دوا", "علاج", "مستشفى", "طبيب"]},
    {"name": "ترفيه", "icon": "clapperboard", "type": "EXPENSE",
     "keywords": ["سينما", "فيلم", "لعبة", "ترفيه", "خروجة", "رحلة"]},
    {"name": "حلاقة وعناية", "icon": "scissors", "type": "EXPENSE",
     "keywords": ["حلاق", "صالون", "حلاقة", "قص شعر"]},
    {"name": "راتب / دخل", "icon": "wallet", "type": "INCOME",
     "keywords": ["راتب", "دخل", "مرتب", "أجرة", "أجر"]},
    {"name": "أخرى", "icon": "tag", "type": "BOTH", "keywords": []},
]


def upgrade() -> None:
    op.bulk_insert(
        categories_table,
        [
            {
                "id": uuid.uuid4(),
                "name": c["name"],
                "icon": c["icon"],
                "is_default": True,
                "category_type": c["type"],
                "keywords": c["keywords"],
                "user_id": None,
            }
            for c in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.execute(
        categories_table.delete().where(categories_table.c.is_default.is_(True))
    )
