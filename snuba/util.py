from flask import request, render_template

from datetime import date, datetime
from dateutil.tz import tz
import json
import jsonschema
import numbers
import requests
import six

import schemas
import settings

def to_list(value):
    return value if isinstance(value, list) else [value]

def column_expr(column_name, body):
    """
    Certain special column names expand into more complex expressions. Return
    the column expression, or just the name if it is a regular column.

    Needs the body of the request for some extra data used to expand column expressions.
    """
    if column_name == settings.TIME_GROUP_COLUMN:
        return settings.TIME_GROUPS.get(body['granularity'], settings.DEFAULT_TIME_GROUP)
    elif column_name == 'issue':
        return issue_expr(body['issues']) if body['issues'] is not None else None
    else:
        return column_name

def escape_literal(value):
    """
    Escape a literal value for use in a SQL clause
    """
    if isinstance(value, six.string_types):
        value = value.replace("'", "\\'") # TODO this escaping is garbage
        return "'{}'".format(value)
    elif isinstance(value, datetime):
        value = value.replace(tzinfo=None, microsecond=0)
        return "toDateTime('{}')".format(value.isoformat())
    elif isinstance(value, date):
        return "toDate('{}')".format(value.isoformat())
    elif isinstance(value, list):
        return "({})".format(', '.join(escape_literal(v) for v in value))
    elif isinstance(value, numbers.Number):
        return str(value)
    else:
        raise ValueError('Do not know how to escape {} for SQL'.format(type(value)))

def raw_query(sql, client):
    """
    Submit a raw SQL query to clickhouse and do some post-processing on it to
    fix some of the formatting issues in the result JSON
    """
    response = client.execute(sql, with_column_types=True)
    # TODO handle query failures / retries
    data, meta = response

    # for now, convert back to a dict-y format to emulate the json
    data = [{c[0]: d[i] for i, c in enumerate(meta)} for d in data]
    meta = [{'name': m[0], 'type': m[1]} for m in meta]

    for col in meta:
        # Convert naive datetime strings back to TZ aware ones, and stringify
	# TODO maybe this should be in the json serializer
        if col['type'] == "DateTime":
            for d in data:
                d[col['name']] = d[col['name']].replace(tzinfo=tz.tzutc()).isoformat()
        if col['type'] == "Date":
            for d in data:
                dt = datetime(*(d[col['name']].timetuple()[:6])).replace(tzinfo=tz.tzutc())
                d[col['name']] = dt.isoformat()

    # TODO record statistics somewhere
    return { 'data': data, 'meta': meta}

def issue_expr(issues, col='primary_hash'):
    """
    Takes a list of (issue_id, fingerprint(s)) tuples of the form:

        [(1, (hash1, hash2)), (2, hash3)]

    and constructs a nested SQL if() expression to return the issue_id of the
    matching fingerprint expression when evaluated on the given column_name.

        if(col in (hash1, hash2), 1, if(col = hash3, 2), NULL)

    """
    if len(issues) == 0:
        return 0
    else:
        issue_id, hashes = issues[0]

        if hasattr(hashes, '__iter__'):
            predicate = "{} IN ('{}')".format(col, "', '".join(hashes))
        else:
            predicate = "{} = '{}'".format(col, hashes)

        return 'if({}, {}, {})'.format(predicate, issue_id, issue_expr(issues[1:], col=col))

def validate_request(schema):
    """
    Decorator to validate that a request body matches the given schema.
    """
    def validator(func):
        def wrapper(*args, **kwargs):

            def default_encode(value):
                if callable(value):
                    return value()
                else:
                    raise TypeError()

            try:
                body = json.loads(request.data)
                schemas.validate(body, schema)
                setattr(request, 'validated_body', body)
            except (ValueError, jsonschema.ValidationError) as e:
                return (render_template('error.html',
                    error=str(e),
                    schema=json.dumps(schema, indent=4, sort_keys=True, default=default_encode)
                ), 400)
            return func(*args, **kwargs)
        return wrapper
    return validator
