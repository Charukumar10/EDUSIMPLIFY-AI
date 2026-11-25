
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = Flask(__name__)

ORCHESTRATE_URL = os.getenv("ORCHESTRATE_URL", "").strip().rstrip("/")
IBM_API_KEY = os.getenv("IBM_API_KEY", "").strip()
AGENT_ID = os.getenv("ORCHESTRATE_AGENT_ID", "").strip()


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")


def get_iam_token():
    response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": IBM_API_KEY
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=30
    )

    response.raise_for_status()
    return response.json()["access_token"]


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()
    language = data.get("language", "English")
    task = data.get("task", "Simplify")

    if not message:
        return jsonify({"reply": "Please enter your study content."}), 400

    if not ORCHESTRATE_URL or not IBM_API_KEY or not AGENT_ID:
        return jsonify({
            "reply": "Missing IBM configuration. Check your .env file."
        }), 500

    try:
        token = get_iam_token()

        endpoint = (
            f"{ORCHESTRATE_URL}/v1/orchestrate/"
            f"{AGENT_ID}/chat/completions"
        )

        prompt = (
            f"Task: {task}\n"
            f"Language: {language}\n"
            f"Study content: {message}\n"
            "Explain accurately in a student-friendly way. "
            "Preserve the original meaning."
        )

        response = requests.post(
            endpoint,
            json={
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=90
        )

        if not response.ok:
            print("Orchestrate error:", response.status_code, response.text[:1000])
            return jsonify({
                "reply": f"IBM Orchestrate returned error {response.status_code}. Check the Flask terminal."
            }), 502

        result = response.json()
        reply = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if isinstance(reply, list):
            reply = "\n".join(
                part.get("text", "")
                for part in reply
                if isinstance(part, dict)
            )

        if not reply:
            print("Unexpected response:", result)
            return jsonify({
                "reply": "Agent responded, but its answer format was unexpected. Check the Flask terminal."
            }), 502

        return jsonify({"reply": reply})

    except requests.RequestException as error:
        print("Connection error:", error)
        return jsonify({
            "reply": "Unable to connect to IBM Orchestrate. Check the Flask terminal."
        }), 502

    except (KeyError, ValueError, IndexError) as error:
        print("Response error:", error)
        return jsonify({
            "reply": "Could not read the agent response. Check the Flask terminal."
        }), 502


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", 5000)),
        debug=True
    )
