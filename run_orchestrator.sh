#!/bin/bash



declare -x FLASK_APP=orchestrator/orchestrator.py
flask run --host=0.0.0.0
