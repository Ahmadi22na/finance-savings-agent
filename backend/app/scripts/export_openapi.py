"""
تصدير توثيق الـ API كملفات ثابتة (بدون ما تحتاج تشغّل السيرفر):

    docker compose exec backend python -m app.scripts.export_openapi

بيكتب بمجلد docs/ (داخل مجلد backend):
  - openapi.json : المواصفة الكاملة (بتنفتح بـ Postman/Insomnia أو أي أداة OpenAPI)
  - API.md       : مرجع مقروء بالعربي لكل الـ Endpoints (للمراجعة أو التسليم لشريك تقني)

خيار اختياري:  --output <مجلد>
"""
import argparse
import json
from pathlib import Path

from app.api.docs import TAGS_METADATA
from app.main import app

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
VALIDATION_DESCRIPTION = "خطأ تحقق من المدخلات (صيغة FastAPI القياسية)."


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _resolve(spec: dict, schema: dict) -> dict:
    if "$ref" in schema:
        return spec["components"]["schemas"][_ref_name(schema["$ref"])]
    return schema


def _type_label(spec: dict, schema: dict) -> str:
    if "$ref" in schema:
        target = _resolve(spec, schema)
        if "enum" in target:
            return "enum: " + " | ".join(str(v) for v in target["enum"])
        return _ref_name(schema["$ref"])
    if "anyOf" in schema:
        labels = [_type_label(spec, option) for option in schema["anyOf"] if option.get("type") != "null"]
        suffix = " (أو null)" if any(option.get("type") == "null" for option in schema["anyOf"]) else ""
        return " | ".join(labels) + suffix
    if schema.get("type") == "array":
        return f"list[{_type_label(spec, schema.get('items', {}))}]"
    label = schema.get("type", "object")
    return f"{label} ({schema['format']})" if "format" in schema else label


def _escape_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _first_example(spec: dict, schema: dict):
    """أول مثال جاهز للمخطط (أو لعناصر القائمة)، أو None."""
    if schema.get("type") == "array":
        item_example = _first_example(spec, schema.get("items", {}))
        return [item_example] if item_example is not None else None
    target = _resolve(spec, schema)
    examples = target.get("examples")
    return examples[0] if examples else None


def _fields_table(spec: dict, schema: dict) -> list[str]:
    target = _resolve(spec, schema)
    properties = target.get("properties", {})
    if not properties:
        return []
    required = set(target.get("required", []))
    rows = ["| الحقل | النوع | مطلوب | الوصف |", "|---|---|---|---|"]
    for name, prop in properties.items():
        rows.append(
            f"| `{name}` | {_escape_cell(_type_label(spec, prop))} | {'نعم' if name in required else 'لا'} "
            f"| {_escape_cell(prop.get('description', ''))} |"
        )
    return rows


def _json_block(value) -> list[str]:
    return ["```json", json.dumps(value, ensure_ascii=False, indent=2), "```"]


def _render_operation(spec: dict, method: str, path: str, op: dict) -> list[str]:
    lines = [f"### {op['summary']}", "", f"`{method.upper()} {path}`", ""]
    lines += [op.get("description", ""), ""]
    lines += [f"**المصادقة:** {'مطلوبة (Bearer)' if op.get('security') else 'غير مطلوبة'}", ""]

    params = [p for p in op.get("parameters", []) if p.get("in") in ("query", "path")]
    if params:
        lines += ["**المعاملات:**", "", "| الاسم | المكان | النوع | الوصف |", "|---|---|---|---|"]
        for p in params:
            lines.append(
                f"| `{p['name']}` | {p['in']} | {_escape_cell(_type_label(spec, p.get('schema', {})))} "
                f"| {_escape_cell(p.get('description', ''))} |"
            )
        lines.append("")

    body = op.get("requestBody", {}).get("content", {})
    if body:
        content_type, content = next(iter(body.items()))
        schema = content.get("schema", {})
        lines += [f"**جسم الطلب** (`{content_type}`):", ""]
        lines += _fields_table(spec, schema) + [""]
        example = _first_example(spec, schema)
        if example is not None:
            lines += ["مثال:", ""] + _json_block(example) + [""]

    lines += ["**الردود:**", "", "| الكود | الوصف |", "|---|---|"]
    for code, response in op["responses"].items():
        description = VALIDATION_DESCRIPTION if code == "422" else response.get("description", "")
        if description == "Successful Response":
            description = "نجاح العملية."
        lines.append(f"| {code} | {_escape_cell(description)} |")
    lines.append("")

    for code in ("200", "201"):
        schema = op["responses"].get(code, {}).get("content", {}).get("application/json", {}).get("schema")
        if schema:
            example = _first_example(spec, schema)
            if example is not None:
                lines += [f"مثال على الرد `{code}`:", ""] + _json_block(example) + [""]
            break
    return lines


def render_markdown(spec: dict) -> str:
    lines = [f"# {spec['info']['title']} — مرجع الـ API", "", f"الإصدار: `{spec['info']['version']}`", ""]
    lines += [spec["info"].get("description", ""), "", "---", ""]

    operations_by_tag: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in spec["paths"].items():
        for method in HTTP_METHODS:
            if method in methods:
                op = methods[method]
                operations_by_tag.setdefault(op["tags"][0], []).append((method, path, op))

    for tag in TAGS_METADATA:
        operations = operations_by_tag.get(tag["name"], [])
        if not operations:
            continue
        lines += [f"## {tag['name']}", "", tag["description"], ""]
        lines += ["| الطريقة | المسار | المصادقة | الملخص |", "|---|---|---|---|"]
        for method, path, op in operations:
            lock = "نعم" if op.get("security") else "لا"
            lines.append(f"| {method.upper()} | `{path}` | {lock} | {_escape_cell(op['summary'])} |")
        lines.append("")
        for method, path, op in operations:
            lines += _render_operation(spec, method, path, op)
        lines += ["---", ""]
    return "\n".join(lines).rstrip() + "\n"


def export(output_dir: Path) -> tuple[Path, Path]:
    spec = app.openapi()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "openapi.json"
    markdown_path = output_dir / "API.md"
    json_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(spec), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    parser = argparse.ArgumentParser(description="تصدير توثيق الـ API (openapi.json + API.md)")
    parser.add_argument("--output", default="docs", help="مجلد الإخراج (الافتراضي: docs)")
    args = parser.parse_args()
    json_path, markdown_path = export(Path(args.output))
    print(f"تم التصدير:\n  {json_path}\n  {markdown_path}")


if __name__ == "__main__":
    main()
