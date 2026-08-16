# Copyright (c) 2024, The Commit Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from openai import OpenAI


class OpenAISettings(Document):
    pass


DOCUMENTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "apis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string"},
                    "path": {"type": "string"},
                    "last_updated": {"type": "string"},
                    "documentation": {"type": "string"},
                },
                "required": [
                    "function_name",
                    "path",
                    "last_updated",
                    "documentation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["apis"],
    "additionalProperties": False,
}


def open_ai_call(message):
    # 1. Get the organization ID and API key from Open API Settings
    open_ai = frappe.get_single("Open AI Settings")
    org_id = open_ai.organization
    api_key = open_ai.get_password("api_key")
    model = open_ai.model

    if not api_key or not model:
        frappe.throw("Please configure the API key and model in Open AI Settings")

    # 2. Initialize the Open AI client
    client = OpenAI(organization=org_id or None, api_key=api_key, timeout=60.0)

    # 2. Make the API call to Open AI
    response = client.responses.create(
        model=model,
        input=message,
        max_output_tokens=open_ai.max_output_tokens or 4000,
        text={
            "format": {
                "type": "json_schema",
                "name": "api_documentation",
                "strict": True,
                "schema": DOCUMENTATION_SCHEMA,
            }
        },
        store=False,
    )

    return response.output_text
