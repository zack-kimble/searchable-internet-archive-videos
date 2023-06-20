import yaml

from searchable_public_meetings import MeetingSeries, SearchableVideo, IAVideoFetcher, Transcriber

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

meeting_series_list = []

for meeting_config in config['meetings']:
    meeting_series_list.append(MeetingSeries.from_config(meeting_config))

fetcher = IAVideoFetcher(start_date=config['start_date'], preferred_formats=config['preferred_formats'])

fetcher.get_videos(meeting_series_list[0])

from faster_whisper import WhisperModel

model_size = "large-v2"

# Run on GPU with FP16
model = WhisperModel(model_size, device="cuda", compute_type="int8")


transcriber = Transcriber(transcribing_model=model)