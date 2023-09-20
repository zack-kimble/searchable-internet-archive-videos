#!/usr/bin/bash
source $HOME/miniconda3/etc/profile.d/conda.sh
set -e
set -a
source zkimble.env
set +a
conda activate searchable_public_meetings
python -u searchable_public_meetings.py
echo "Completed updating markdown"
bash -i update_md_repo.sh
