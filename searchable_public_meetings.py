import json
import logging
import re

logger = logging.getLogger(__name__)

import os
from datetime import datetime, timedelta

from internetarchive import get_item, download, get_session, configure, File
from ffmpeg import FFmpeg

from pathlib import Path

from tabulate import tabulate

from more_itertools import chunked


def chunk_write_md_file(md_path, i, header: str, body_lines: list, max_bytes=345 * 1000):
    bytes_written = 0
    with open(md_path.with_stem(f"{md_path.stem}_{i}"), 'wb') as f:
        bytes_written += f.write(header.encode('utf-8'))
        for l, line in enumerate(body_lines):
            line = line+'\n'
            bytes_written += f.write(line.encode('utf-8'))
            if bytes_written >= max_bytes:
                break
    if l < len(body_lines) - 1:
        chunk_write_md_file(md_path, i + 1, header, body_lines[l+1:], max_bytes)


class TextSegment:
    def __init__(self, start, end, text, url_with_timestamp):
        self.start = start
        self.end = end
        self.text = text
        self.url_with_timestamp = url_with_timestamp

    @classmethod
    def from_json(cls, fp):
        segment_dict = json.load(fp)
        return cls.from_dict(segment_dict)

    @classmethod
    def from_dict(cls, segment_dict):
        segment = cls(
            start=segment_dict['start'],
            end=segment_dict['end'],
            text=segment_dict['text'],
            url_with_timestamp=segment_dict['url_with_time']
            )
        return segment


    def to_dict(self):
        return {
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'url_with_time': self.url_with_timestamp
        }

    def to_json(self, fp):
        json.dump(self.to_dict(), fp)


class SearchableVideo:
    def __init__(self, identifier, video_series): #, url=None, title=None, date=None, video_file=None, audio_file=None):
        self.identifier = identifier
        self.video_series = video_series
        self._url = None
        self._title = None
        self._date = None
        self._full_text = None
        self._segment_file = None
        self._video_file_name = None

        self.file_identifier = self.__getattribute__(self.video_series.file_identifier)


        video_suffix = Path(self.video_file_name).suffix
        #have to convert paths back to strings because av doesn't handle Path objects
        self._video_file = str(Path(self.video_series.video_dir).joinpath(self.file_identifier).with_suffix(video_suffix))
        self._audio_file = str(Path(self.video_series.audio_dir).joinpath(f'{self.file_identifier}').with_suffix('.mp3'))
        self._markdown_file = str(Path(self.video_series.markdown_dir).joinpath(f'{self.file_identifier}').with_suffix('.md'))
        self._segment_file = str(Path(self.video_series.segment_dir).joinpath(f'{self.file_identifier}').with_suffix('.json'))

    # def get_video_file_name(self):
    #     self._video_file_name = self.video_series.video_fetcher.get_video_file_name(self.identifier)
    #     self._video_file_path = Path(self.video_series.video_dir).joinpath(self._video_file_name)


    @classmethod
    def from_json(cls, json):
        video = cls(json['identifier'], json['url'], json['title'], json['date'])
        video.full_text = json['full_text']
        video.segments = [TextSegment.from_json(segment) for segment in json['segments']]
        video.video_file = json['video_file']
        video.audio_file = json['audio_file']
        return video

    @property
    def segment_file(self):
        if not Path(self._segment_file).exists():
            logger.info(f"Segments for {self.identifier} do not exist.")
            logger.info(f"Transcribing {self.identifier} from {self.audio_file} to segments.")
            segments, info = self.video_series.transcriber.transcribe(self.audio_file)
            text_segments = [
                TextSegment(int(segment.start), segment.end, segment.text, self.create_url_with_timestamp(int(segment.start)))
                for segment in segments]
            with open(self._segment_file, 'w') as fp:
                json.dump([segment.to_dict() for segment in text_segments], fp)

        return self._segment_file

    def create_url_with_timestamp(self, timestamp):
        return f"{self.url}?start={timestamp}"

    @property
    def full_text(self):
        return ''.join(self.segments)

    @property
    def audio_file(self):
        if not Path(self._audio_file).exists():
            logger.info(f"Audio file {self._audio_file} does not exist.")
            logger.info(f"Converting {self.video_file} to audio for {self.identifier}")
            self._audio_file = video2audio(self.video_file, self._audio_file)
        return self._audio_file

    @property
    def video_file(self):
        if not Path(self._video_file).exists():
            logger.info(f"Video file {self._video_file} does not exist.")
            logger.info(f"Downloading {self.identifier} video to {self._video_file}")
            self._video_file = self.video_series.video_fetcher.download_video_file(
                self.identifier, self._video_file_name, self._video_file)
        return self._video_file

    def _update_metadata(self):
        self._url, self._title, self._date = self.video_series.video_fetcher.get_video_metadata(
            self.identifier)
    @property
    def video_file_name(self):
        if not self._video_file_name:
            self._video_file_name = self.video_series.video_fetcher.get_video_file_name(self.identifier)
            #TODO: this is a hack to handle videos that don't have a preferred format
            if not self._video_file_name:
                with open(self._markdown_file, 'w') as f:
                    f.write(f"Video file not found for {self.identifier}")
                self._video_file_name = f"None.mp4"
        return self._video_file_name

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

    def to_dict(self):
        return {
            'identifier': self.identifier,
            'url': self.url,
            'title': self.title,
            'date': self.date,
            'full_text': self.full_text,
            'segments': [segment.to_dict() for segment in self.segments],
            'video_file': self.video_file,
            'audio_file': self.audio_file
        }

    @property
    def markdown_file(self):
        #TODO: add a glob to check for split md files
        if not Path(self._markdown_file).exists():
            logger.info(f"Markdown file {self._markdown_file} does not exist.")
            _ = self._write_markdown_file()
        return self._markdown_file

    @staticmethod
    def prettify_segment(segment:dict):
        #TODO: Clean this and _write_markdown_file up. Shouldn't have headers defined in two spots and ordering should be explicit
        pretty_segment = {}
        pretty_segment['Time'] = str(timedelta(seconds=int(segment['start'])))
        pretty_segment['Transcript'] = segment['text']
        pretty_segment['Video'] = f"[source video]({segment['url_with_time']})"
        return (pretty_segment.values())

    @staticmethod
    def remove_md_table_whitespace(md):
        return re.sub(' *(?=\|)', '', md)



    def _write_markdown_file(self):
        logger.info(f"Writing {self.identifier} markdown to {self._markdown_file}")
        with open(self.segment_file, 'r') as fp:
            segments_list = json.load(fp)
        # only write 1300 segments at a time so that github can still index for search
        md_path = Path(self._markdown_file)
        values_list = [self.prettify_segment(segment) for segment in segments_list]
        segments_md = tabulate(values_list, tablefmt='github', headers=['Time', 'Transcript', 'Video'])
        md = ''.join([f"## [{self.title}]({self.url})\n",
                      f"### {self.date}\n",
                      segments_md])
        md = self.remove_md_table_whitespace(md)
        md_lines = md.splitlines()
        md_header = '\n'.join(md_lines[0:4])+ '\n'
        md_body_lines = md_lines[4:]
        chunk_write_md_file(md_path, 0, md_header, md_body_lines)

        #
        # for i, chunk in enumerate(chunked(segments_list, n=2000)):
        #     values_list = [self.prettify_segment(segment) for segment in chunk]
        #     segments_md = tabulate(values_list, tablefmt='github', headers=['Time', 'Transcript', 'Video'])
        #
        #     md = ''.join([f"## [{self.title}]({self.url})\n",
        #                   f"### {self.date}\n",
        #                   segments_md])
        #     md = self.remove_md_table_whitespace(md)
        #     with open(md_path.with_stem(f'{md_path.stem}_{i}'), 'w') as md_file:
        #         md_file.write(md)
       # try:

        # except FileNotFoundError as e:
        #     Path(self.md_file_path).parent.mkdir(parents=True)
        #     with open(self.md_file_path, 'w') as md_file:
        #         md_file.write(md)
        return self._markdown_file


class VideoSeries:
    def __init__(self, name, ia_seach_query, video_dir='video', audio_dir='audio',
                 segment_dir='segment', markdown_dir='markdown', data_dir='data',
                 file_identifier='title',
                 video_fetcher=None, transcriber=None):
        self.name = name
        self.ia_seach_query = ia_seach_query
        self.videos = {}
        self.video_fetcher = video_fetcher
        self.transcriber = transcriber
        self.data_dir = data_dir
        self.video_dir = Path(data_dir).joinpath(video_dir).joinpath(name)
        self.audio_dir = Path(data_dir).joinpath(audio_dir).joinpath(name)
        self.segment_dir = Path(data_dir).joinpath(segment_dir).joinpath(name)
        self.markdown_dir = Path(data_dir).joinpath(markdown_dir).joinpath(name)
        self.file_identifier = file_identifier

        Path(self.video_dir).mkdir(parents=True, exist_ok=True)
        Path(self.audio_dir).mkdir(parents=True, exist_ok=True)
        Path(self.segment_dir).mkdir(parents=True, exist_ok=True)
        Path(self.markdown_dir).mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config, video_fetcher=None, transcriber=None):
        return cls(name=config['name'], ia_seach_query=config['ia_search_query'],
                   video_fetcher=video_fetcher, transcriber=transcriber)

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

    def write_all_videos_to_md(self):
        for video in self.videos.values():
            video.markdown_file


class IAVideoFetcher:
    def __init__(self, preferred_formats=['h.264'], start_date=None):
        # See if you can replace with access keys
        assert os.getenv('IA_USERNAME') and os.getenv(
            'IA_PASSWORD'), "IA_USERNAME and IA_PASSWORD environment variables must be set"
        configure(username=os.getenv('IA_USERNAME'), password=os.getenv('IA_PASSWORD'))
        self.session = get_session()
        self.preferred_formats = preferred_formats
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

    def get_video_file_name(self, identifier):
        item = get_item(identifier)
        for file in item.files:
            # TODO: find smallest video file
            if file['format'].lower() in self.preferred_formats:
                return file['name']
        logger.warning(f'No video in preferred format found for {identifier}')
        return

    def download_video_file(self, identifier, file_name, target_filepath):
        item = get_item(identifier)
        logger.info(f'Downloading {identifier}:{file_name}')
        file_obj = File(item, file_name)
        file_obj.download(file_path=str(target_filepath))
        return target_filepath


    def get_video_metadata(self, identifier):
        item = get_item(identifier)
        return item.urls.details, item.metadata['title'], item.metadata['date']

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


def video2audio(video_fp, audio_fp):
    # audio_fn = f'{Path(video_fp).stem}.mp3'
    # if not Path(audio_dir).exists():
    #     Path(audio_dir).mkdir()
    # audio_fp = f'{audio_dir}/{audio_fn}'
    ffmpeg = (
        FFmpeg()
        .option("vn")
        .option('y')
        .input(video_fp)
        .output(audio_fp, {'ar': 16000}))
    ffmpeg.execute()
    return audio_fp


if __name__ == '__main__':
    # updates identifiers for each video series in config and then writes them to markdown. Any missing videos
    # are downloaded and transcribed.

    from faster_whisper import WhisperModel
    import ruamel.yaml as yaml
    import logging
    import requests_cache

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    logger.addHandler(logging.FileHandler('searchable_public_meetings.log'))

    requests_cache.install_cache('ia_cache', backend='sqlite', expire_after=60*60)

    config = yaml.safe_load(open('config.yaml'))

    model = WhisperModel(config['model_size'],
                         device="cuda",
                         compute_type=config['compute_type']
                         )

    transcriber = Transcriber(transcribing_model=model)

    fetcher = IAVideoFetcher(start_date=config['start_date'],
                             preferred_formats=config['preferred_formats'])
    for video_series_config in config['meeting_video_series']:
        video_series = VideoSeries.from_config(config=video_series_config,
                                               video_fetcher=fetcher, transcriber=transcriber)
        video_series.update_identifiers()
        video_series.write_all_videos_to_md()

