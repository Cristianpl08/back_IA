from flask import Blueprint, request, jsonify, send_file
import os
import re
import time
from pydub import AudioSegment
from elevenlabs import ElevenLabs, save
import json
import requests
import os
import google.auth.transport.requests
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from flask import Flask, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import json

# Crear un Blueprint para las rutas
api_bp = Blueprint('api', __name__)

# Configurar Eleven Labs API
ELEVEN_LABS_API_KEY = "sk_8faef5ef41cf2b42a3605a9350d5ad3a7b437b72ff7c84e1"
client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)

VOICE_IDS = {
    "Default": "gUABw7pXQjhjt0kNFBTF",
    "Narrator": "gUABw7pXQjhjt0kNFBTF",
    "Skoop": "gUABw7pXQjhjt0kNFBTF",
    "Whirly": "gUABw7pXQjhjt0kNFBTF",
    "Dumper": "gUABw7pXQjhjt0kNFBTF"
}

@api_bp.route('/get-voices', methods=['GET'])
def get_voices():
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "xi-api-key": ELEVEN_LABS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            voices = response.json().get("voices", [])
            return jsonify({"voices": voices}), 200
        else:
            return jsonify({"error": "Failed to fetch voices", "details": response.text}), response.status_code
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

def text_to_speech_eleven_labs(text, voice_id, model, output_file):
    audio = client.generate(
        text=text,
        voice=voice_id,
        model=model
    )
    save(audio, output_file)
    while not os.path.exists(output_file):
        time.sleep(0.1)
    return audio

def parse_srt(srt_file):
    with open(srt_file, 'r') as file:
        content = file.read()

    pattern = re.compile(r'\d+\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)', re.DOTALL)
    matches = pattern.findall(content)

    parsed_data = []
    last_voice = "Default"
    any_voice_found = False

    for start, end, text in matches:
        voice = "Default"
        
        voice_match = re.match(r'([A-Za-z]+):', text)
        if voice_match:
            voice = voice_match.group(1).strip()
            text = re.sub(r'^([A-Za-z]+):', '', text).strip()
            last_voice = voice
            any_voice_found = True
        else:
            voice = last_voice
        
        text = re.sub(r'\*(.*?)\*', '', text).strip()

        parsed_data.append((start, end, text, voice))

    if not any_voice_found:
        parsed_data = [(start, end, text, "Default") for (start, end, text, _) in parsed_data]

    return parsed_data

@api_bp.route('/parse-srt', methods=['POST'])
def parse_srt_file():
    if 'srt_file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    srt_file = request.files['srt_file']
    srt_path = "temp_script.srt"
    srt_file.save(srt_path)

    parsed_srt = parse_srt(srt_path)

    return jsonify({"parsed_srt": parsed_srt})

def timecode_to_milliseconds(timecode):
    hours, minutes, seconds = timecode.split(':')
    seconds, milliseconds = seconds.split(',')
    total_milliseconds = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(milliseconds)
    return total_milliseconds

def generate_audio_segments(parsed_srt, model, voice_ids, voice_name_to_id):
    audio_segments = []
    previous_end_ms = 0

    for i, (start, end, text, voice) in enumerate(parsed_srt):
        start_ms = timecode_to_milliseconds(start)
        end_ms = timecode_to_milliseconds(end)
        duration_ms = end_ms - start_ms

        current_voice_id = voice_name_to_id.get(voice, VOICE_IDS["Default"])

        if start_ms > previous_end_ms:
            silence_duration_ms = start_ms - previous_end_ms
            silence = AudioSegment.silent(duration=silence_duration_ms)
            audio_segments.append(silence)

        audio_file = f'audio_{i}.mp3'
        text_to_speech_eleven_labs(text, current_voice_id, model, audio_file)

        audio_segment = AudioSegment.from_mp3(audio_file)
        if len(audio_segment) > duration_ms:
            speed_factor = len(audio_segment) / duration_ms
            audio_segment = audio_segment.speedup(playback_speed=speed_factor)

        if len(audio_segment) < duration_ms:
            silence_duration_ms = duration_ms - len(audio_segment)
            silence = AudioSegment.silent(duration=silence_duration_ms)
            audio_segment = audio_segment + silence

        audio_segments.append(audio_segment)
        os.remove(audio_file)

        previous_end_ms = end_ms

    final_silence = AudioSegment.silent(duration=30000)
    audio_segments.append(final_silence)

    return audio_segments

def combine_audio_segments(audio_segments, output_file):
    final_audio = sum(audio_segments)
    final_audio.export(output_file, format="mp3")
    print(f"Final audio exported to {output_file}.")

@api_bp.route('/process-srt', methods=['POST'])
def process_srt_file():
    if 'srt_file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    srt_file = request.files['srt_file']
    srt_path = "temp_script.srt"
    srt_file.save(srt_path)

    final_file_name = request.form.get('final_file_name', 'output.mp3')
    model = request.form.get('model', 'eleven_turbo_v2')

    voice_ids = request.form.get('voice_ids')
    voice_names = request.form.get('voice_names')

    if voice_ids:
        voice_ids = json.loads(voice_ids)
    else:
        voice_ids = []

    if voice_names:
        voice_names = json.loads(voice_names)
    else:
        voice_names = []

    if len(voice_ids) != len(voice_names):
        return jsonify({"error": f"Expected {len(voice_names)} voice IDs but got {len(voice_ids)}"}), 400

    voice_name_to_id = {name: voice_ids[i] for i, name in enumerate(voice_names)}

    parsed_srt = parse_srt(srt_path)
    
    audio_segments = generate_audio_segments(parsed_srt, model, voice_ids, voice_name_to_id)
    final_audio_file = f"{final_file_name}.mp3"
    combine_audio_segments(audio_segments, final_audio_file)

    return send_file(final_audio_file, as_attachment=True)
