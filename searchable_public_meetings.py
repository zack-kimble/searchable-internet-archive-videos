import logging
logger = logging.getLogger(__name__)

import os
from datetime import datetime, timedelta
from pathlib import Path

from internetarchive import get_item, download, get_session, configure, File
from ffmpeg import FFmpeg

from pathlib import Path

class TextSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text

    @classmethod
    def from_json(cls, json):
        return cls(json['start'], json['end'], json['text'])

class SearchableVideo:
    def __init__(self, identifier, video_series, url=None, title=None, date=None, video_file=None, audio_file=None):
        self.identifier = identifier
        self.video_series = video_series
        self._url = url
        self._title = title
        self._date = date
        self._full_text = None
        self._segments = None
        self._video_file = video_file
        self._audio_file = audio_file

    @classmethod
    def from_json(cls, json):
        video = cls(json['identifier'], json['url'], json['title'], json['date'])
        video.full_text = json['full_text']
        video.segments = json['segments']
        video.video_file = json['video_file']
        video.audio_file = json['audio_file']
        return video

    @property
    def segments(self):
        if not self._segments:
            logger.info(f"Transcribing {self.identifier}")
            segments, info = self.video_series.transcriber.transcribe(self.audio_file)
            self._segments = [TextSegment(segment.start, segment.end, segment.text)
                              for segment in segments]
        return self._segments

    @property
    def full_text(self):
        return ''.join(self.segments)

    @property
    def audio_file(self):
        if not (self._audio_file and Path(self._audio_file).exists()):
            logger.info(f"Extracting {self.identifier} audio")
            self._audio_file = video2audio(self.video_file)
        return self._audio_file

    @property
    def video_file(self):
        if not (self._video_file and Path(self._video_file).exists()):
            logger.info(f"Downloading {self.identifier} video")
            target_dir_path = Path(self.video_series.name).joinpath(self.identifier)
            self._video_file = self.video_series.video_fetcher.get_video_file(
                self.identifier, target_dir_path)
        return self._video_file

    def _update_metadata(self):
        self._url, self._title, self._date = self.video_series.video_fetcher.get_video_metadata(
            self.identifier)
    @property
    def url(self):
        if not self._url:
            self._update_metadata()
        return self._url

    @property
    def title(self):
        if not self._title:
            self._update_metadata()
        return self._title

    @property
    def date(self):
        if not self._date:
            self._update_metadata()
        return self._date


class VideoSeries:
    def __init__(self, name, ia_seach_query, video_fetcher=None, transcriber=None):
        self.name = name
        self.ia_seach_query = ia_seach_query
        self.videos = {}
        self.video_fetcher = video_fetcher
        self.transcriber = transcriber

    @classmethod
    def from_config(cls, config, video_fetcher=None, transcriber=None):
        return cls(config['name'], config['ia_search_query'], video_fetcher, transcriber)

    @classmethod
    def from_json(cls, json, video_fetcher=None, transcriber=None):
        video_series = cls(json['name'], json['ia_seach_query'])
        video_series.videos = [SearchableVideo.from_json(video_json) for video_json in json['videos']]
        video_series.video_fetcher = video_fetcher
        video_series.transcriber = transcriber
        return video_series

    def update_identifiers(self):
        indentifiers = self.video_fetcher.get_video_series_identifiers(self)
        for identifier in indentifiers:
            if identifier not in self.videos:
                self.videos[identifier] = SearchableVideo(identifier, self)

class IAVideoFetcher:
    def __init__(self, preferred_formats=['h.264'], video_dir='videos', start_date=None):
        # See if you can replace with access keys
        assert os.getenv('IA_USERNAME') and os.getenv('IA_PASSWORD'), "IA_USERNAME and IA_PASSWORD environment variables must be set"
        configure(username=os.getenv('IA_USERNAME'), password=os.getenv('IA_PASSWORD'))
        self.session = get_session()
        self.preferred_formats = preferred_formats
        self.video_dir = video_dir
        if start_date:
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            self.start_date = datetime.today().date() - timedelta(days=31)
        self.end_date = datetime.today().date() + timedelta(days=1)


    def get_video_series_identifiers(self, video_series):
        date_constrained_query = self.add_date_to_query(video_series.ia_seach_query)
        search_results = self.session.search_items(date_constrained_query)
        search_identifiers = [x['identifier'] for x in search_results]
        # for identifier in search_identifiers:
        #     if identifier not in video_series.videos:
        #         self._get_video(identifier, video_series.name)
        return search_identifiers

    def add_date_to_query(self, query):
        return f'({query}) AND date:[{self.start_date} TO {self.end_date}]'


    def get_video_file(self, identifier, target_dir):
        item = get_item(identifier)
        for file in item.files:
            #TODO: find smallest video file
            if file['format'].lower() in self.preferred_formats:
                video_fp = f'{self.video_dir}/{target_dir}/{file["name"]}'
                logger.info(f'Downloading {identifier}')
                file_obj = File(item, file['name'])
                file_obj.download(file_path=video_fp)
                return video_fp
        logger.warning(f'No preferred format found for {identifier}')
        return

    def get_video_metadata(self, identifier):
        item = get_item(identifier)
        return  item.urls.details, item.metadata['title'], item.metadata['date']

    # def get_video_date(self, identifier):
    #     item = get_item(identifier)
    #     return
    #
    # def get_video_url(self, identifier):
    #     item = get_item(identifier)
    #     return

class Transcriber:
    def __init__(self, transcribing_model):
        self.transcribing_model = transcribing_model
    def transcribe(self, audio_fp):
        segments, info = self.transcribing_model.transcribe(audio_fp, beam_size=5)
        return segments, info

def video2audio(video_fp, audio_dir='audio'):
    audio_fn = f'{Path(video_fp).stem}.mp3'
    if not Path(audio_dir).exists():
        Path(audio_dir).mkdir()
    audio_fp = f'{audio_dir}/{audio_fn}'
    ffmpeg = (
              FFmpeg()
              .option("vn")
              .option('y')
              .input(video_fp)
              .output(audio_fp, {'ar':16000}))
    ffmpeg.execute()
    return audio_fp

class StateManager:
    def __init__(self, video_series, ):
        pass


class PagesManager:
    pass






                # for format in self.preferred_formats:
                #     result = item.download(format=format)
                #     if len(result) > 0:
                #         break
