import pytest

from copy import deepcopy

from snuba.clickhouse.columns import ColumnSet
from snuba.datasets.schemas.tables import TableSource
from snuba.query.expressions import Column, CurriedFunctionCall, FunctionCall, Literal
from snuba.query.processors.basic_functions import BasicFunctionsProcessor
from snuba.query.query import Query
from snuba.request.request_settings import HTTPRequestSettings

test_data = [
    (
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                FunctionCall("alias", "uniq", (Column(None, "column1", None),)),
                FunctionCall("alias2", "emptyIfNull", (Column(None, "column2", None),)),
            ],
        ),
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                FunctionCall(
                    "alias",
                    "ifNull",
                    (
                        FunctionCall(None, "uniq", (Column(None, "column1", None),)),
                        Literal(None, 0),
                    ),
                ),
                FunctionCall(
                    "alias2",
                    "ifNull",
                    (
                        FunctionCall(
                            None, "emptyIfNull", (Column(None, "column2", None),)
                        ),
                        Literal(None, ""),
                    ),
                ),
            ],
        ),
    ),  # Single simple uniq + emptyIfNull
    (
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                Column(None, "column1", None),
                FunctionCall("alias", "uniq", (Column(None, "column1", None),)),
                FunctionCall("alias2", "emptyIfNull", (Column(None, "column2", None),)),
            ],
            condition=FunctionCall(
                None, "eq", (Column(None, "column1", None), Literal(None, "a"))
            ),
            groupby=[
                FunctionCall("alias3", "uniq", (Column(None, "column5", None),)),
                FunctionCall("alias4", "emptyIfNull", (Column(None, "column6", None),)),
            ],
        ),
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                Column(None, "column1", None),
                FunctionCall(
                    "alias",
                    "ifNull",
                    (
                        FunctionCall(None, "uniq", (Column(None, "column1", None),)),
                        Literal(None, 0),
                    ),
                ),
                FunctionCall(
                    "alias2",
                    "ifNull",
                    (
                        FunctionCall(
                            None, "emptyIfNull", (Column(None, "column2", None),)
                        ),
                        Literal(None, ""),
                    ),
                ),
            ],
            condition=FunctionCall(
                None, "eq", (Column(None, "column1", None), Literal(None, "a"))
            ),
            groupby=[
                FunctionCall(
                    "alias3",
                    "ifNull",
                    (
                        FunctionCall(None, "uniq", (Column(None, "column5", None),)),
                        Literal(None, 0),
                    ),
                ),
                FunctionCall(
                    "alias4",
                    "ifNull",
                    (
                        FunctionCall(
                            None, "emptyIfNull", (Column(None, "column6", None),)
                        ),
                        Literal(None, ""),
                    ),
                ),
            ],
        ),
    ),  # Complex query with both uniq and emptyIfNull
    (
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                CurriedFunctionCall(
                    None,
                    FunctionCall(None, "top", (Literal(None, 10),)),
                    (Column(None, "column1", None),),
                )
            ],
        ),
        Query(
            {},
            TableSource("events", ColumnSet([])),
            selected_columns=[
                CurriedFunctionCall(
                    None,
                    FunctionCall(None, "topK", (Literal(None, 10),)),
                    (Column(None, "column1", None),),
                )
            ],
        ),
    ),
]


@pytest.mark.parametrize("pre_format, expected_query", test_data)
def test_format_expressions(pre_format: Query, expected_query: Query) -> None:
    copy = deepcopy(pre_format)
    BasicFunctionsProcessor().process_query(copy, HTTPRequestSettings())
    assert (
        copy.get_selected_columns_from_ast()
        == expected_query.get_selected_columns_from_ast()
    )
    assert copy.get_groupby_from_ast() == expected_query.get_groupby_from_ast()
    assert copy.get_condition_from_ast() == expected_query.get_condition_from_ast()
