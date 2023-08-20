import shutil
from pathlib import Path

from searchable_public_meetings import VideoSeries, SearchableVideo, IAVideoFetcher, Transcriber, video2audio
import pytest
import ruamel.yaml as yaml

from faster_whisper import WhisperModel

@pytest.fixture(scope="session", autouse=True)
def clean_up_data_dir():
    shutil.rmtree('data', ignore_errors=True)
    yield
    # forgoing cleanup
    #shutil.rmtree('data', ignore_errors=True)

@pytest.fixture
def test_config():
    with open('test_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return config

@pytest.fixture
def test_transcriber(test_config):
    model_size = "large-v2"
    # Run on GPU with FP16
    model = WhisperModel(model_size, device="cuda", compute_type="int8")
    transcriber = Transcriber(transcribing_model=model)

    return transcriber

@pytest.fixture
def test_fetcher(test_config):
    fetcher = IAVideoFetcher(start_date=test_config['start_date'],
                             preferred_formats=test_config['preferred_formats'])
    return fetcher


@pytest.fixture
def test_video_series(test_config, test_fetcher, test_transcriber):
    test_video_series = VideoSeries.from_config(test_config['meeting_video_series'][0],
                                                test_fetcher, test_transcriber)
    return test_video_series

# def test_update_identifiers(test_video_series):
#     test_video_series.update_identifiers()
#     assert len(test_video_series.videos) ==2
#     assert test_video_series.videos['ertsgsdfgdsf']
#     assert test_video_series.videos['walmartcommerical']
#
# def test_fetcher_get_video_series_identifiers(test_video_series, test_fetcher):
#     identifiers = test_fetcher.get_video_series_identifiers(test_video_series)
#     assert identifiers == ['ertsgsdfgdsf', 'walmartcommerical']

def test_get_segments(test_video_series):
    test_video_series.update_identifiers()
    segments = test_video_series.videos['ertsgsdfgdsf'].segments
    assert len(segments) == 3
    assert segments[0].start == 0.0

def test_video2audio():
    Path('test_assets/Oprah Commerical - CTV.mp3').unlink(missing_ok=True)
    video2audio('test_assets/Oprah Commerical - CTV.mp4', 'test_assets')
    assert Path('test_assets/Oprah Commerical - CTV.mp3').exists()
    Path('test_assets/Oprah Commerical - CTV.mp3').unlink()


def test_SearchableVideo_to_markdown(test_video_series):

    test_video_series.update_identifiers()
    test_video_series.videos['ertsgsdfgdsf'].to_markdown_file("data/markdown/test_ertsgsdfgdsf.md")
    with open("data/markdown/test_ertsgsdfgdsf.md", 'r') as f:
        contents = f.read()
    assert contents # not sure how to test this. Maybe there's a md validator out there.

def test_VideoSeries_write_all_videos_to_md(test_video_series):
    test_video_series.update_identifiers()
    test_video_series.write_all_videos_to_md()
    assert Path(f"data/markdown/{test_video_series.name}/Walmart Commerical.md").exists()
    assert Path(f"data/markdown/{test_video_series.name}/Oprah Commerical - CTV.md").exists()