"""
Config — إعدادات التطبيق الأساسية.
هاد Skeleton فقط، لسا بدون منطق فعلي (المشروع بمرحلة Discovery).
راجع قسم 3 و 4 بتوثيق AI Coding Context قبل التوسع هون.
"""

import os


class Config:
    """إعدادات مشتركة لكل البيئات."""
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Provider — قابل للتبديل (قسم 3)
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
