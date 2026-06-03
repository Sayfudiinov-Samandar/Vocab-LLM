#!/bin/bash
set -e

mkdir -p data

uvicorn backend.main:app --host 0.0.0.0 --port 8000