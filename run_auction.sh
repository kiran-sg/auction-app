#!/bin/bash

echo "Activating virtual environment..."
source /Users/kiransg97/work/angular/python/.venv/bin/activate

echo "Checking Streamlit..."
pip install streamlit

echo "Starting Hero Cup Auction App..."
streamlit run "/Users/kiransg97/work/angular/python/HERO CUP/auction_app.py"
