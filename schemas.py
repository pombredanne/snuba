from datetime import datetime, timedelta
import jsonschema

QUERY_SCHEMA = {
    'type': 'object',
    'properties': {
        'conditions': {
            'type': 'array',
            'items': {
                'type': 'array',
                'items': [
                    {
                        # Column name
                        'type': 'string',
                        'pattern': '^[a-zA-Z0-9_]+$',
                    },{
                        # Operator
                        'type': 'string',
                        'enum': ['>', '<', '>=', '<=', '=', 'IN'],
                    },{
                        # Literal
                        'anyOf': [
                            {'type': ['string', 'number']},
                            {
                                'type': 'array',
                                'items': {'type': ['string', 'number']}
                            },
                        ],
                    },
                ],
                'minLength': 3,
                'maxLength': 3,
            },
            'default': list,
        },
        'from_date': {
            'type': 'string',
            'format': 'date-time',
            'default': lambda: (datetime.utcnow().replace(microsecond=0) - timedelta(days=5)).isoformat()
        },
        'to_date': {
            'type': 'string',
            'format': 'date-time',
            'default': lambda: datetime.utcnow().replace(microsecond=0).isoformat()
        },
        'granularity': {
            'type': 'number',
            'default': 3600,
        },
        'issues': {
            'type': 'array',
            'items': {
                'type': 'array',
                'minItems': 2,
                'maxItems': 2,
                'items': [
                    {'type': 'number'},
                    {
                        'anyOf': [
                            {"$ref": "#/definitions/fingerprint_hash"},
                            {
                                'type': 'array',
                                'items': {"$ref": "#/definitions/fingerprint_hash"},
                                'minItems': 1,
                            },
                        ],
                    },
                ],
            },
            'default': list,
        },
        'project': {
            'anyOf': [
                {'type': 'number'},
                {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 1,
                },
            ]
        },
        'groupby': {
            'anyOf': [
                {'enum': ['issue']}, # Special computed column created from `issues` definition
                {
                    'type': 'string',
                    # TODO make sure its a valid column, either in the schema or here
                    'pattern': '^[a-zA-Z0-9_]+$',
                },
            ],
            'default': 'issue',
        },
        'aggregateby': {
            'type': 'string',
            'pattern': '^[a-zA-Z0-9_]*$',
            'default': '',
        },
        'aggregation': {
            'type': 'string',
            'default': 'count',
            'anyOf': [
                {'enum': ['count', 'uniq']},
                {'pattern': 'topK\(\d+\)'},
            ],
        },
    },
    'required': ['project'], # Need to select down to the project level for customer isolation and performance

    'definitions': {
        'fingerprint_hash': {
            'type': 'string',
            'minLength': 16,
            'maxLength': 16,
            'pattern': '^[0-9a-f]{16}$',
        }
    }
}

def validate(value, schema, set_defaults=True):
    orig = jsonschema.Draft4Validator.VALIDATORS["properties"]

    def validate_and_default(validator, properties, instance, schema):
        for property, subschema in properties.iteritems():
            if "default" in subschema:
                if callable(subschema["default"]):
                    instance.setdefault(property, subschema["default"]())
                else:
                    instance.setdefault(property, subschema["default"])

        for error in orig(validator, properties, instance, schema):
            yield error

    validator_cls = jsonschema.validators.extend(
        jsonschema.Draft4Validator,
        {'properties': validate_and_default}
    ) if set_defaults else jsonschema.Draft4Validator

    validator_cls(
        schema,
        types={'array': (list, tuple)},
        format_checker=jsonschema.FormatChecker()
    ).validate(value, schema)