"""Regression tests for explicit Web API success-response contracts."""

from __future__ import annotations

from typing import Any


def _success_responses(openapi: dict[str, Any]) -> list[tuple[str, str, str, dict[str, Any]]]:
    responses: list[tuple[str, str, str, dict[str, Any]]] = []
    for path, path_item in openapi["paths"].items():
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if operation is None:
                continue
            for status_code, response in operation["responses"].items():
                if str(status_code).startswith("2"):
                    responses.append((method.upper(), path, str(status_code), response))
    return responses


def _is_unconstrained_schema(schema: dict[str, Any]) -> bool:
    return not schema or schema == {"type": "object", "additionalProperties": True}


def test_every_web_api_operation_has_an_explicit_success_contract() -> None:
    from fastapi.routing import APIRoute

    from lifeos_web.app import create_app

    app = create_app()
    api_routes = [
        nested_route
        for route in app.routes
        for nested_route in getattr(getattr(route, "original_router", None), "routes", [route])
        if isinstance(nested_route, APIRoute)
    ]
    inventory = sorted(
        (
            method,
            route.path,
            str(route.status_code or 200),
            route.response_model,
        )
        for route in api_routes
        for method in route.methods or set()
    )

    assert len(inventory) == 119
    missing = [
        f"{method} {path} ({status_code})"
        for method, path, status_code, response_model in inventory
        if status_code != "204" and response_model is None
    ]
    nonempty_204 = [
        f"{method} {path}"
        for method, path, status_code, response_model in inventory
        if status_code == "204" and response_model is not None
    ]

    assert missing == []
    assert nonempty_204 == []


def test_openapi_success_responses_are_concrete_and_204_responses_are_empty() -> None:
    from lifeos_web.app import create_app

    responses = _success_responses(create_app().openapi())
    assert len(responses) == 119

    failures: list[str] = []
    for method, path, status_code, response in responses:
        content = response.get("content", {})
        if status_code == "204":
            if content:
                failures.append(f"{method} {path} returns content for 204")
            continue

        schema = content.get("application/json", {}).get("schema")
        if schema is None or _is_unconstrained_schema(schema):
            failures.append(f"{method} {path} ({status_code}) has no concrete JSON schema")
        elif schema.get("type") == "array" and _is_unconstrained_schema(schema.get("items", {})):
            failures.append(f"{method} {path} ({status_code}) has unconstrained list items")

    assert failures == []


def test_dynamic_json_values_are_an_explicit_recursive_union() -> None:
    from lifeos_web.app import create_app

    schema = create_app().openapi()["components"]["schemas"]["JsonValue"]
    variants = schema["anyOf"]

    assert {variant.get("type") for variant in variants} == {
        "array",
        "boolean",
        "integer",
        "null",
        "number",
        "object",
        "string",
    }
    assert {"$ref": "#/components/schemas/JsonValue"} in [
        variant.get("items") for variant in variants
    ]
