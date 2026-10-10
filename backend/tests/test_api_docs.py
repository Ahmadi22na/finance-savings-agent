"""
حراس جودة توثيق الـ API: أي Endpoint جديد لازم ينوثّق (ملخص + وصف + Tag معرّف + 401 للمحمي)،
وإلا الاختبار بيفشل. وكمان بنتأكد إنه تصدير التوثيق (openapi.json + API.md) بيشتغل.
"""
import json

import pytest

from app.api.docs import TAGS_METADATA
from app.main import app
from app.scripts.export_openapi import export, render_markdown

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
PUBLIC_PATHS = {"/health", "/api/v1/personas", "/api/v1/auth/register", "/api/v1/auth/login"}


@pytest.fixture(scope="module")
def spec():
    return app.openapi()


def _operations(spec):
    for path, methods in spec["paths"].items():
        for method in HTTP_METHODS:
            if method in methods:
                yield method, path, methods[method]


def test_every_operation_has_summary_and_description(spec):
    undocumented = [
        f"{method.upper()} {path}"
        for method, path, op in _operations(spec)
        if not op.get("summary") or not op.get("description")
    ]
    assert undocumented == []


def test_every_tag_is_declared_with_a_description(spec):
    declared = {tag["name"]: tag["description"] for tag in spec["tags"]}
    used = {op["tags"][0] for _, _, op in _operations(spec)}
    assert used <= set(declared)
    assert all(declared[name] for name in used)
    assert [tag["name"] for tag in TAGS_METADATA] == [tag["name"] for tag in spec["tags"]]


def test_protected_operations_document_401(spec):
    for method, path, op in _operations(spec):
        if path in PUBLIC_PATHS:
            continue
        assert "401" in op["responses"], f"{method.upper()} {path} لا يوثّق 401"
        assert op.get("security"), f"{method.upper()} {path} لا يظهر كمحمي بالـ Swagger"


def test_request_bodies_have_examples(spec):
    """كل Request Body JSON لازم يكون له مثال جاهز (بتعبّي Swagger تلقائيًا)."""
    schemas = spec["components"]["schemas"]
    for method, path, op in _operations(spec):
        content = op.get("requestBody", {}).get("content", {}).get("application/json")
        if not content:
            continue
        name = content["schema"]["$ref"].rsplit("/", 1)[-1]
        assert schemas[name].get("examples"), f"{name} (في {method.upper()} {path}) بدون examples"


def test_export_writes_json_and_markdown(tmp_path):
    json_path, markdown_path = export(tmp_path / "docs")

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert "/api/v1/agent/actions/{action_id}/confirm" in exported["paths"]

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "POST /api/v1/transactions/scan-receipt" in markdown
    assert "تأكيد اقتراح وتنفيذه" in markdown
    assert "## Transactions" in markdown


def test_markdown_lists_every_operation(spec):
    markdown = render_markdown(spec)
    for method, path, _ in _operations(spec):
        assert f"`{method.upper()} {path}`" in markdown
