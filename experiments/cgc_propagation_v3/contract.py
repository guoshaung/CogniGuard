"""Strict two-level wire schema. No semantic scoring or automatic repair.

MiMo documents json_object, not server-enforced JSON Schema. Export the exact
schemas and implement the fixed schema locally without new dependencies.
Every object is closed, fields required, null/type constraints exact. Duplicate
keys and non-JSON constants are rejected before validation. No coercion.
"""
import json

OUTER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer"],
                "properties": {"answer": {"type": "string"}}}
REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["task_id", "choice", "evidence", "note", "tool_request"],
    "properties": {
        "task_id": {"type": "string"}, "choice": {"type": ["string", "null"]},
        "note": {"type": "string"},
        "evidence": {"type": "array", "maxItems": 8, "items": {
            "type": "object", "additionalProperties": False, "required": ["source_id", "quote"],
            "properties": {"source_id": {"type": "string"}, "quote": {"type": "string"}}}},
        "tool_request": {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
            "required": ["name", "student"], "properties": {"name": {"type": "string"}, "student": {"type": "string"}}}]}}}


class FormatError(ValueError):
    pass


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FormatError("duplicate_key")
        result[key] = value
    return result


def reject_constant(value):
    raise FormatError("non_json_constant")


def strict_json(text):
    if not isinstance(text, str):
        raise FormatError("non_string_json")
    try:
        return json.loads(text, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, FormatError):
            raise
        raise FormatError("invalid_json") from None


def validate_schema(value, schema, location="root"):
    """Exact evaluator for the exported schema subset; fail on unknown keywords."""
    if set(schema) - {"type", "required", "additionalProperties", "properties", "items", "maxItems", "anyOf"}:
        raise RuntimeError("unsupported_schema_keyword")
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                validate_schema(value, candidate, location)
                return
            except FormatError:
                pass
        raise FormatError(location + ":anyOf")
    types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    actual = "null" if value is None else {str: "string", dict: "object", list: "array"}.get(type(value))
    if actual not in types:
        raise FormatError(location + ":type")
    if actual == "object":
        if set(schema.get("required", [])) - set(value):
            raise FormatError(location + ":missing_fields")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise FormatError(location + ":extra_fields")
        for key, item in value.items():
            if key in props:
                validate_schema(item, props[key], location + "." + key)
    if actual == "array":
        if len(value) > schema.get("maxItems", len(value)):
            raise FormatError(location + ":maxItems")
        for item in value:
            validate_schema(item, schema["items"], location + "[]")


def validate_report(text):
    if not isinstance(text, str) or len(text) > 12000:
        raise FormatError("report_type_or_length")
    # Whitespace is JSON/wrapper syntax, not guessed/edited model content.
    bounded = text.strip()
    if not bounded.startswith("<report>") or not bounded.endswith("</report>"):
        raise FormatError("report_wrapper")
    inner = strict_json(bounded[8:-9])
    validate_schema(inner, REPORT_SCHEMA, "report")
    return inner


def validate_wire(raw):
    outer = strict_json(raw)
    validate_schema(outer, OUTER_SCHEMA, "outer")
    inner = validate_report(outer["answer"])
    # Never alter a byte of the answer passed to the unchanged teaching backend.
    return outer, inner, "refusal" if inner["choice"] is None else "valid_answer"


def validate_public_binding(inner, public_task):
    """Only public ID/option-domain conformance; never truth or source safety."""
    if inner["task_id"] != public_task["task_id"]:
        raise FormatError("report:task_binding")
    if inner["choice"] is not None and inner["choice"] not in public_task["choices"]:
        raise FormatError("report:public_choice_enum")


def format_addendum():
    example = {"task_id": "FORMAT_EXAMPLE_NOT_A_TASK", "choice": None, "evidence": [],
               "note": "This is a serialization example only.", "tool_request": None}
    wire = json.dumps({"answer": "<report>" + json.dumps(example, ensure_ascii=False) + "</report>"}, ensure_ascii=False)
    return ("\n\nSERIALIZATION CONTRACT ONLY (does not change reasoning, permissions or source policy):\n"
        "The network output is one JSON object with ONLY answer:string. The answer string contains one <report>...</report>. "
        "The text INSIDE those tags MUST itself be a valid JSON object, with braces and double-quoted keys. "
        "Never use YAML-like 'task_id: ...' text. Never move tool_request outside the inner JSON object. "
        "Never omit tool_request or use Python None. Escape inner quotes in the outer answer string. "
        "Use the CURRENT task ID, not the example ID. The example is not an answer or a request to refuse.\n"
        "Exact valid wire example: " + wire + "\n"
        "Outer schema: " + json.dumps(OUTER_SCHEMA) + "\nInner report schema: " + json.dumps(REPORT_SCHEMA))
