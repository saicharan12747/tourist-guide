import base64
import os
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"
load_dotenv(Path(__file__).with_name(".env"))

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

PROMPTS = {
    "Summary": """
You are a professional tourist guide.
Provide a high-level overview of "{place}" in {language}.

Focus on:
- The historical significance
- Why the place is famous
- Key architectural or cultural highlights

Keep the explanation concise, engaging, and easy to follow.
Avoid excessive details and dates.
Limit the response to around 200 words.
s
Respond ONLY in {language}.
""",

    "Detailed": """
You are a professional tourist guide.
Provide a detailed and immersive explanation of "{place}" in {language}.

Cover:
- Historical background and timeline
- Architectural design and unique features
- Cultural importance and notable events
- Interesting facts and visitor insights

Explain concepts clearly and in a storytelling manner.
Include relevant details and examples to create a rich experience.
Limit the response to around 400 words.

Respond ONLY in {language}.
"""
}

def generate_speech(text, voice_id, locale, api_key):
    url = "https://global.api.murf.ai/v1/speech/stream"
    headers = {
        "api-key": api_key.strip(),
        "Content-Type": "application/json"
    }
    data = {
        "voice_id": voice_id,
        "text": text,
        "locale": locale,
        "model": "FALCON",
        "format": "MP3",
        "sampleRate": 24000,
        "channelType": "MONO"
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=(10, 120)
    )
    response.raise_for_status()
    return response.content


def generate_description(place, answer_type, language, api_key):
    prompt = PROMPTS[answer_type].format(place=place, language=language)
    client = genai.Client(api_key=api_key.strip())
    response = None
    last_error = None
    models = ("gemini-3.1-flash-lite", "gemini-flash-lite-latest")
    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            break
        except APIError as error:
            last_error = error
            if error.code in (404, 503) and model != models[-1]:
                continue
            raise

    if response is None:
        raise last_error
    if not response.text:
        raise RuntimeError("The text generation service returned an empty response.")
    return response.text


@app.get("/health")
def health():
    missing_api_keys = [
        key for key in ("GEMINI_API_KEY", "MURF_API_KEY")
        if not os.getenv(key, "").strip()
    ]
    return jsonify(
        status="ok",
        configured=not missing_api_keys,
        missingApiKeys=missing_api_keys
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def index(path):
    if path and (FRONTEND_DIR / path).exists():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/generate-audio-guide", methods=["POST"])
def generate_audio_guide():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    required_fields = ("place", "answerType", "language", "voiceId", "locale")
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify(
            error="Missing required fields: " + ", ".join(missing_fields)
        ), 400

    answer_type = data["answerType"]
    if answer_type not in PROMPTS:
        return jsonify(error="answerType must be Summary or Detailed."), 400

    missing_api_keys = [
        key for key in ("GEMINI_API_KEY", "MURF_API_KEY")
        if not os.getenv(key, "").strip()
    ]
    if missing_api_keys:
        return jsonify(
            error=(
                "Audio generation is not configured. Add "
                + ", ".join(missing_api_keys)
                + " as backend environment variables and restart the backend."
            )
        ), 503

    try:
        text_description = generate_description(
            data["place"],
            answer_type,
            data["language"],
            os.environ["GEMINI_API_KEY"].strip()
        )
        audio_bytes = generate_speech(
            text_description,
            data["voiceId"],
            data["locale"],
            os.environ["MURF_API_KEY"].strip()
        )
    except APIError as error:
        app.logger.exception("Gemini text generation failed")
        if error.code == 503:
            return jsonify(
                error="Gemini is temporarily overloaded. Please try again shortly."
            ), 503
        if error.code == 429:
            return jsonify(
                error="Gemini API quota is temporarily unavailable. Please try again later."
            ), 503
        if error.code in (401, 403):
            return jsonify(
                error="Gemini rejected the API key. Check the GEMINI_API_KEY setting."
            ), 502
        return jsonify(
            error="Gemini could not generate the guide. Please try again later."
        ), 502
    except requests.RequestException:
        app.logger.exception("Murf speech generation failed")
        return jsonify(error="Murf could not generate audio. Check your API key, quota, and connection."), 502
    except RuntimeError as error:
        app.logger.exception("Audio guide generation failed")
        return jsonify(error=str(error)), 502

    return jsonify(
        description=text_description,
        audioBase64=base64.b64encode(audio_bytes).decode("utf-8")
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )