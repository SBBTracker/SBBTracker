#!/usr/bin/env bash

. venv/Scripts/activate
pytest
test_status=$?
deactivate
exit $test_status
