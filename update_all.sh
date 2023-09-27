#!/usr/bin/bash
source $HOME/miniconda3/etc/profile.d/conda.sh
set -e
set -a
source zkimble.env
set +a
conda activate searchable_internet_archive_videos
python -u searchable_internet_archive_videos.py
echo "Completed updating markdown"
bash -i update_md_repo.sh
