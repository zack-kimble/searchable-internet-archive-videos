#!/usr/bin/bash
echo "Moving markdown to knox_searchable_meetings_md repo"
mkdir -p ~/knox_searchable_meetings_md/meetings
rm -rf ~/knox_searchable_meetings_md/meetings/*
cp -rf data/markdown/* ~/knox_searchable_meetings_md/meetings/
cd ~/knox_searchable_meetings_md/
git add .
git commit -m "Update markdown files"
#ssh-keygen -H -F github.com
echo "Pushing to github"
git push