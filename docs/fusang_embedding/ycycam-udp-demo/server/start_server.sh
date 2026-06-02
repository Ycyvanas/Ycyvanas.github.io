#!/bin/bash
cd "$(dirname "$0")"
source /home/dx1991/anaconda3/etc/profile.d/conda.sh
conda activate ycyserver
python3 web_receiver.py
