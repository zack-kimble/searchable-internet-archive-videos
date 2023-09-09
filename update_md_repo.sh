#!/bin/bash
set -e
mkdir -p ~/knox_searchable_meetings_md/meetings
rm -rf ~/knox_searchable_meetings_md/meetings/*
cp -rf data/markdown/* ~/knox_searchable_meetings_md/meetings/
cd ~/knox_searchable_meetings_md/
git add .
git commit -m "Update markdown files"
git push