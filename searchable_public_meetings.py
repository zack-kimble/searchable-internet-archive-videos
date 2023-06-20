import logging
logger = logging.getLogger(__name__)

import os
from datetime import datetime, timedelta
from pathlib import Path

from internetarchive import get_item, download, get_session, configure, File
from ffmpeg import FFmpeg

class SearchableVideo:
    def __init__(self, identifier, url, title, date):
        self.identifier = identifier
        self.url = url
        self.title = title
        self.date = date
        self.full_text = ''
        self.segments = []

    @classmethod
    def from_json(cls, json):
        video = cls(json['identifier'], json['url'], json['title'], json['date'])
        video.full_text = json['full_text']
        video.segments = json['segments']
        return video


class MeetingSeries:
    def __init__(self, name, ia_seach_query):
        self.name = name
        self.ia_seach_query = ia_seach_query
        self.videos = []

    @classmethod
    def from_config(cls, config):
        return cls(config['name'], config['ia_search_query'])

    @classmethod
    def from_json(cls, json):
        meeting_series = cls(json['name'], json['ia_seach_query'])
        meeting_series.videos = [SearchableVideo.from_json(video_json) for video_json in json['videos']]

class IAVideoFetcher:
    def __init__(self, preferred_formats=['h.264'], video_dir='videos', start_date=None):
        # See if you can replace with access keys
        configure(username=os.getenv('IA_USERNAME'), password=os.getenv('IA_PASSWORD'))
        self.session = get_session()
        self.preferred_formats = preferred_formats
        self.video_dir = video_dir
        if start_date:
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            self.start_date = datetime.date.today() - datetime.timedelta(days=31)
        self.end_date = datetime.today().date() + timedelta(days=1)


    def get_videos(self, meeting_series):
        date_constrained_query = self.add_date_to_query(meeting_series.ia_seach_query)
        search_results = self.session.search_items(date_constrained_query)
        search_identifiers = [x['identifier'] for x in search_results]
        for identifier in search_identifiers:
            if identifier not in meeting_series.videos:
                self._get_video(identifier, meeting_series.name)


    def add_date_to_query(self, query):
        return query + f' AND date:[{self.start_date} TO {self.end_date}]'


    def _get_video(self, identifier, download_dir):
        item = get_item(identifier)
        for file in item.files:
            if file['format'].lower() in self.preferred_formats:
                logger.info(f'Downloading {identifier}')
                file_obj = File(item, file['name'])
                file_obj.download(file_path=f'{self.video_dir}/{download_dir}/{file["name"]}')
                break
        logger.warning(f'No preferred format found for {identifier}')


class Transcriber:
    def __init__(self, transcribing_model):
        self.transcribing_model = transcribing_model
        audio_dir = 'audio'
    def transcribe(self, video_fp):
        audio = self.video2audio(video_fp)
        segments, info = self.transcribing_model.transcribe(audio, beam_size=5)

    def video2audio(self, video_fp):
        audio_fn = f'{Path(video_fp).stem}.mp3'
        audio_fp = f'{self.audio_dir}/{audio_fn}'
        ffmpeg = (
                  FFmpeg()
                  .option("vn")
                  .input(video_fp)
                  .output(audio_fp, {'ar:16000'}))
        ffmpeg.execute()


class StateManager:
    def __init__(self, meeting_series, ):
        pass


class PagesManager:
    pass






                # for format in self.preferred_formats:
                #     result = item.download(format=format)
                #     if len(result) > 0:
                #         break
