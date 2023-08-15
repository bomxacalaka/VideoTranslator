import moviepy.editor as mp
from moviepy.editor import VideoFileClip
import whisper
import numpy as np
from moviepy.audio.AudioClip import AudioArrayClip
import os
import shutil
from datetime import timedelta
import os
import whisper
import openai
from googletrans import Translator, constants
from pprint import pprint
from gtts import gTTS, langs
import subprocess
import shlex


class VideoTransformFile:
    # Constructor
    def __init__(self, input_path):
        self.media_path = input_path
        self.video_name = os.path.basename(input_path).split('.')[0]
        self.transcript = None

    # Get audio from video
    def get_audio(self):
        clip = mp.VideoFileClip(self.media_path)
        audio = clip.audio
        return audio

    # Save audio to tmp folder
    def save_audio_tmp(self):
        # if not os.path.exists("tmp"):
        #     os.mkdir("tmp")
        # audio = self.get_audio()
        # file = f"tmp/{self.video_name}.wav"
        # audio = audio.write_audiofile(file)
        # return audio, file
        if not os.path.exists("tmp"):
            os.mkdir("tmp")
        file = f"tmp/{self.video_name}.wav"
        ffmpeg_command = f"ffmpeg -y -i {self.media_path} -vn -acodec pcm_s16le -ar 44100 -ac 2 {file}"
        subprocess.call(shlex.split(ffmpeg_command))
        return file
    
    # Get transcript from audio
    def get_transcript(self):
        model = whisper.load_model('base')
        file = self.save_audio_tmp()
        transcript = model.transcribe(file)
        self.transcript = transcript
        return transcript
    
    # Get srt file from transcript
    def get_srt(self):
        if self.transcript is None:
            self.get_transcript()
        segments = self.transcript['segments']

        if not os.path.exists("SrtFiles"):
            os.mkdir("SrtFiles")

        for segment in segments:
            startTime = str(0)+str(timedelta(seconds=int(segment['start'])))+',000'
            endTime = str(0)+str(timedelta(seconds=int(segment['end'])))+',000'
            text = segment['text']
            segmentId = segment['id']+1
            segment = f"{segmentId}\n{startTime} --> {endTime}\n{text[1:] if text[0] is ' ' else text}\n\n"

            srtFilename = os.path.join("SrtFiles", f"{self.video_name}.srt")
            with open(srtFilename, 'a', encoding='utf-8') as srtFile:
                srtFile.write(segment)

        return srtFilename
    

    # Get translated srt file
    def translateSrt(self, language: str, output: str = None):
        if self.transcript is None:
            self.get_transcript()
        segments = self.transcript['segments']
        
        if not os.path.exists("SrtFiles") and output is None:
            os.mkdir("SrtFiles")
            output = os.path.join("SrtFiles", f"{self.video_name}.srt")
            
        if len(language) > 2:
            languages = constants.LANGUAGES
            # Look for English
            for lang in languages:
                if language.lower() in languages[lang]:
                    language = lang
        translator = Translator()

        for segment in segments:
            startTime = str(0)+str(timedelta(seconds=int(segment['start'])))+',000'
            endTime = str(0)+str(timedelta(seconds=int(segment['end'])))+',000'
            text = translator.translate(segment['text'], dest=language).text
            segmentId = segment['id']+1
            segment = f"{segmentId}\n{startTime} --> {endTime}\n{text[1:] if text[0] is ' ' else text}\n\n"

            with open(output, 'a', encoding='utf-8') as srtFile:
                srtFile.write(segment)

        return output
    
    # Text to cloned speech
    def textToSpeech(self, text: str, output: str = None, language: str = None):
        if len(language) > 2:
            languages = langs._langs
            # Look for English
            for lang in languages:
                if language.lower() in languages[lang].lower():
                    language = lang
                    

        myobj = gTTS(text=text, lang=language, slow=False)

        if output is None:
            output = os.path.join("AudioFiles", f"{self.video_name}.mp3")
            if not os.path.exists("AudioFiles"):
                os.mkdir("AudioFiles")
        myobj.save(output)


    # Get translated audio
    def translateAudio(self, language: str, output: str = None):
        if self.transcript is None:
            self.get_transcript()
        segments = self.transcript['segments']
        
        if not os.path.exists("AudioFiles") and output is None:
            os.mkdir("AudioFiles")
            output = os.path.join("AudioFiles", f"{self.video_name}.mp3")

        if not os.path.exists("tmp"):
            os.mkdir("tmp")
            
        if len(language) > 2:
            languages = constants.LANGUAGES
            # Look for English
            for lang in languages:
                if language.lower() in languages[lang].lower():
                    dest_language = lang
        translator = Translator()

        files = []
        for segment in segments:
            text = translator.translate(segment['text'], dest=dest_language).text
            self.textToSpeech(text, f"tmp/{segment['id']}.wav", language)
            files.append(f"tmp/{segment['id']}.wav")


        # Merge audio files
        command = f"ffmpeg -y -i \"concat:{'|'.join(files)}\" -acodec copy tmp/{self.video_name}_trans.wav"
        subprocess.call(shlex.split(command))

        # Get length of output audio
        ffprobe_command = f"ffprobe -i tmp/{self.video_name}_trans.wav -show_entries format=duration -v quiet -of csv=\"p=0\""
        audio_length = float(subprocess.check_output(ffprobe_command, shell=True))

        ffprobe_command = f"ffprobe -i {self.media_path} -show_entries format=duration -v quiet -of csv=\"p=0\""
        video_length = float(subprocess.check_output(ffprobe_command, shell=True))

        
        
        # Speed up audio to match video length
        # video_length = VideoFileClip(self.media_path).duration
        print(audio_length, video_length)
        ffmpeg_command = f"ffmpeg -y -i tmp/{self.video_name}_trans.wav -filter:a \"atempo={audio_length/video_length}\" -vn {output}"
        subprocess.call(shlex.split(ffmpeg_command))
        print(ffmpeg_command)
        print(output)

        return output
    

    # Get translated video
    def translateVideo(self, language: str, output: str = None):
        
        if not os.path.exists("VideoFiles") and output is None:
            os.mkdir("VideoFiles")
            output = os.path.join("VideoFiles", f"{self.video_name}.mp4")

        # Get translated audio
        if os.path.exists(f"tmp/{self.video_name}_translated.wav"):
            audio = f"tmp/{self.video_name}_translated.wav"
        else:
            audio = self.translateAudio(language, f"tmp/{self.video_name}_translated.wav")

        # Get original video
        video = self.media_path

        # Merge audio and video
        ffmpeg_command = f"ffmpeg -y -i {video} -i {audio} -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 {output}"
        subprocess.call(shlex.split(ffmpeg_command))

        return output
    

    # Get translated video with subtitles
    def translateVideoWithSubtitles(self, language: str, output: str = None):
        if self.transcript is None:
            self.get_transcript()
        segments = self.transcript['segments']
        
        if not os.path.exists("VideoFiles") and output is None:
            os.mkdir("VideoFiles")
            output = os.path.join("VideoFiles", f"{self.video_name}.mp4")

        # Get original video
        video = self.translateVideo(language, f"tmp/{self.video_name}_translated.mp4")

        # Get translated srt file
        if os.path.exists(f"tmp/{self.video_name}_translated.srt"):
            srt = f"tmp/{self.video_name}_translated.srt"
        else:
            srt = self.translateSrt(language, f"tmp/{self.video_name}_translated.srt")

        # Merge audio and video
        ffmpeg_command = f"ffmpeg -y -i {video} -vf subtitles={srt} {output}"
        subprocess.call(shlex.split(ffmpeg_command))

        return output
    
    
    # Delete temporary files
    def deleteTmpFiles(self):
        if os.path.exists("tmp"):
            shutil.rmtree("tmp")
        # if os.path.exists("AudioFiles"):
        #     shutil.rmtree("AudioFiles")
        # if os.path.exists("SrtFiles"):
        #     shutil.rmtree("SrtFiles")
        # if os.path.exists("VideoFiles"):
        #     shutil.rmtree("VideoFiles")