#
# Copyright (c) 2021 Airbyte, Inc., all rights reserved.
#

import random
import string
from functools import partial
from typing import Iterable
from unittest.mock import Mock

import pytest
from docker.errors import ContainerError
from source_acceptance_test.utils.compare import make_hashable
from source_acceptance_test.utils.connector_runner import ConnectorRunner


def not_sorted_data():
    return {
        "date_created": "0001-01-01T00:00:00",
        "date_updated": "0001-01-01T00:00:00",
        "editable": False,
        "id": "superuser",
        "name": "Super User",
        "organization_id": "orga_ya3w9oMjeLtWe7zFGZr63Dz8ruBbjybG0EIUdUXaESi",
        "permissions": [
            "bulk_edit",
            "delete_own_opportunities",
            "export",
            "manage_group_numbers",
            "manage_email_sequences",
            "delete_leads",
            "call_coach_listen",
            "call_coach_barge",
            "manage_others_tasks",
            "manage_others_activities",
            "delete_own_tasks",
            "manage_customizations",
            "manage_team_smart_views",
            "bulk_delete",
            "manage_team_email_templates",
            "bulk_email",
            "merge_leads",
            "calling",
            "bulk_sequence_subscriptions",
            "bulk_import",
            "delete_own_activities",
            "manage_others_opportunities",
        ],
    }


def sorted_data():
    return {
        "date_created": "0001-01-01T00:00:00",
        "date_updated": "0001-01-01T00:00:00",
        "editable": False,
        "id": "superuser",
        "name": "Super User",
        "organization_id": "orga_ya3w9oMjeLtWe7zFGZr63Dz8ruBbjybG0EIUdUXaESi",
        "permissions": [
            "bulk_delete",
            "bulk_edit",
            "bulk_email",
            "bulk_import",
            "bulk_sequence_subscriptions",
            "call_coach_barge",
            "call_coach_listen",
            "calling",
            "delete_leads",
            "delete_own_activities",
            "delete_own_opportunities",
            "delete_own_tasks",
            "export",
            "manage_customizations",
            "manage_email_sequences",
            "manage_group_numbers",
            "manage_others_activities",
            "manage_others_opportunities",
            "manage_others_tasks",
            "manage_team_email_templates",
            "manage_team_smart_views",
            "merge_leads",
        ],
    }


@pytest.mark.parametrize(
    "obj1,obj2,is_same",
    [
        (sorted_data(), not_sorted_data(), True),
        (
            {
                "organization": {
                    "features": [
                        "issue-percent-filters",
                        "performance-tag-page",
                    ]
                }
            },
            {
                "organization": {
                    "features": [
                        "performance-tag-page",
                        "issue-percent-filters",
                    ]
                }
            },
            True,
        ),
        (
            {
                "organization": {
                    "features": [
                        "issue-percent-filters",
                        "performance-tag-page",
                    ]
                }
            },
            {
                "organization": {
                    "features": [
                        "performance-tag-pag",
                        "issue-percent-filters",
                    ]
                }
            },
            False,
        ),
        (
            {
                "organization": {
                    "features": [
                        "issue-percent-filters",
                        "performance-tag-page",
                    ]
                }
            },
            {
                "organization": {
                    "features": [
                        "performance-tag-page",
                    ]
                }
            },
            False,
        ),
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}, True),
        ({"a": 1, "b": 2, "c": {"d": [1, 2]}}, {"b": 2, "a": 1, "c": {"d": [2, 1]}}, True),
        ({"a": 1, "b": 2, "c": {"d": [1, 2]}}, {"b": 2, "a": 1, "c": {"d": [3, 4]}}, False),
    ],
)
def test_compare_two_records_nested_with_different_orders(obj1, obj2, is_same):
    """Test that compare two records with equals, not sorted data."""
    output_diff = set(map(make_hashable, [obj1])).symmetric_difference(set(map(make_hashable, [obj2])))
    if is_same:
        assert not output_diff, f"{obj1} should be equal to {obj2}"
    else:
        assert output_diff, f"{obj1} shouldnt be equal to {obj2}"


def test_exclude_fields():
    """Test that check ignoring fields"""
    data = [
        sorted_data(),
    ]
    ignored_fields = [
        "organization_id",
    ]
    serializer = partial(make_hashable, exclude_fields=ignored_fields)
    output = map(serializer, data)
    for item in output:
        assert "organization_id" not in item


class MockContainer:
    def __init__(self, status: dict, iter_logs: Iterable):
        self.wait = Mock(return_value=status)
        self.logs = Mock(return_value=iter(iter_logs))

        class Image:
            pass

        self.image = Image()


def binary_generator(lengths, last_line=None):
    data = ""
    for length in lengths:
        data += "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length)) + "\n"
    data = data.encode()
    chunk_size = random.randint(512, 1024)

    while len(data) > chunk_size:
        yield data[:chunk_size]
        data = data[chunk_size:]
    yield data
    if last_line:
        yield ("bla-1234567890-bla\n" + last_line).encode()


def test_successful_logs_reading():
    line_count = 1234
    line_lengths = [random.randint(0, 1024 * 20) for _ in range(line_count)]
    lines = [
        line for line in ConnectorRunner.read(container=MockContainer(status={"StatusCode": 0}, iter_logs=binary_generator(line_lengths)))
    ]
    assert line_count == len(lines)
    for line, length in zip(lines, line_lengths):
        assert len(line) - 1 == length


@pytest.mark.parametrize(
    "traceback,container_error,last_line,expected_error",
    (
        # container returns a some internal error
        (
            "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nKeyError: 'bbbb'",
            "Some Container Error",
            "Last Container Logs Line",
            "Some Container Error",
        ),
        # container returns a raw traceback
        (
            "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nKeyError: 'bbbb'",
            None,
            "Last Container Logs Line",
            "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nKeyError: 'bbbb'",
        ),
        # container doesn't return any tracebacks or errors
        (
            None,
            None,
            "Last Container Logs Line",
            "Last Container Logs Line",
        ),
    ),
)
def test_failed_reading(traceback, container_error, last_line, expected_error):
    line_count = 10
    line_lengths = [random.randint(0, 523) for _ in range(line_count)]

    with pytest.raises(ContainerError) as exc:
        list(
            ConnectorRunner.read(
                container=MockContainer(
                    status={"StatusCode": 1, "Error": container_error}, iter_logs=binary_generator(line_lengths, traceback or last_line)
                )
            )
        )

    assert expected_error == exc.value.stderr
