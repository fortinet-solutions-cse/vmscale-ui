#!/bin/bash



declare -x FLASK_APP=orchestrator/orchestrator.py
flask run
