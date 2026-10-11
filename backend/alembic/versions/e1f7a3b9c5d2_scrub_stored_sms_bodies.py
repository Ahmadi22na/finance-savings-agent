"""scrub stored sms bodies (data minimization)

كانت معاملات الرسائل البنكية بتخزّن نص الرسالة كامل (فيه الرصيد ورقم الهاتف) بعمود raw_source_data،
وما في أي كود بيقراه. بنمسحه من السجلات القديمة؛ والسجلات الجديدة ما عادت تخزّنه.
بصمة منع التكرار (external_ref) ما بتتأثر.

Revision ID: e1f7a3b9c5d2
Revises: d4a9c6e1f2b7
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e1f7a3b9c5d2'
down_revision: Union[str, None] = 'd4a9c6e1f2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE transactions SET raw_source_data = NULL WHERE source = 'SMS'")


def downgrade() -> None:
    # البيانات الممسوحة ما بترجع (مقصود).
    pass
