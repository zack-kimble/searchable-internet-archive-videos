# Searchable internet Archive Videos
## Overview

This is a barebones tool for fidning and downloading videos from the Internet Archive, transcribing them, and putting the transcriptiosn into markdown. The end result are files that can be easily searched with links to the timestamp in the video. Allowing effective text search of the videos contents.

The code was originally written to support a specific use case in Knoxville, TN (https://github.com/zack-kimble/knox_searchable_meetings_md). Hence the single config.

## Usage

Install dependencies `conda env create -f conda_env.yaml`

Obtain an IA API key and set `IA_USERNAME` and `IA_PASSWORD` environment variables.

Update `config.yaml` with the desired search terms. You may also need to change model size and prefered format.

run `searchable_internet_archive_videos.py`

# Known TODO
* Stop using properties to manage the pipeline. Long running property methods are not debugger friendly.
* Move bash scripts and config to a separate repo.