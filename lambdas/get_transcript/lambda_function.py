import json
import os
import urllib.request
import urllib.error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def _error(status_code, message):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        return _error(500, "ASSEMBLYAI_API_KEY environment variable is not set.")

    qs = event.get("queryStringParameters") or {}
    transcript_id = qs.get("id")

    if not transcript_id:
        return _error(400, "Query parameter 'id' is required.")

    url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    req = urllib.request.Request(
        url,
        headers={"authorization": api_key},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = str(e)

        if status_code == 404:
            return _error(
                404,
                "Transcript not found (404). Verify the transcript id and that the job exists.",
            )
        if status_code == 401:
            return _error(401, "Invalid API key")

        return _error(502, f"AssemblyAI HTTP error {status_code}: {error_body}")
    except urllib.error.URLError as e:
        return _error(502, f"Error connecting to AssemblyAI: {e.reason}")

    status = data.get("status")

    base = {
        "status": status,
        "transcriptId": data.get("id"),
    }

    if status == "completed":
        response_body = {
            **base,
            "text": data.get("text"),
            "confidence": data.get("confidence"),
            "audioDuration": data.get("audio_duration"),
            "words": data.get("words"),
        }
    elif status == "error":
        response_body = {
            **base,
            "status": "error",
            "error": data.get("error", "Unknown error from AssemblyAI"),
        }
    else:
        response_body = base

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_body),
    }

