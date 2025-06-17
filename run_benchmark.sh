#!/bin/bash
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
export PYTHONPATH="$PYTHONPATH:$SCRIPT_DIR/sources"
python sources/run_benchmark.py