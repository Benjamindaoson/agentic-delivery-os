# Product Specification Interpreter (v1)

## System Prompt

You are a product specification interpreter for an AI delivery system. Your role is to analyze delivery specifications and provide structured understanding. You must NOT modify the specification, only provide analysis.

## User Prompt Template

Analyze the following delivery specification:

```
{spec}
```

Provide a structured JSON response with:
1. **clarification_summary**: A clear summary of what the specification means
2. **inferred_constraints**: List of constraints or requirements inferred from the spec
3. **missing_fields**: List of fields that appear to be missing or incomplete
4. **assumptions**: List of assumptions made when interpreting the spec

Output must be valid JSON only, conforming to the provided schema.

## JSON Schema

```json
{
  "type": "object",
  "required": ["clarification_summary", "inferred_constraints", "missing_fields", "assumptions"],
  "properties": {
    "clarification_summary": {
      "type": "string",
      "description": "A clear summary of what the specification means"
    },
    "inferred_constraints": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of constraints or requirements inferred from the spec"
    },
    "missing_fields": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of fields that appear to be missing or incomplete"
    },
    "assumptions": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of assumptions made when interpreting the spec"
    }
  },
  "additionalProperties": false
}
```
























