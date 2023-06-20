import whisper
#from ffmpeg import FFmpeg, Progress



# ffmpeg = (
#     FFmpeg()
#     .option("y")
#     .input("input.mp4")
#     .output(
#         "ouptut.mp3",
#         {"codec:v": "libx264"},
#         vf="scale=1280:-1",
#         preset="veryslow",
#         crf=24,
#     )
# )
#
# ffmpeg.execute()



model = whisper.load_model("base")
result = model.transcribe("/home/zack/PycharmProjects/searchable-audio/tests/test_assets/searchable_audio_test_1.wav")

x=1