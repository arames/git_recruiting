#!/bin/bash
cd "$(dirname "$0")"
git fetch --prune
git checkout origin/main
python3 gitcontrib.py
