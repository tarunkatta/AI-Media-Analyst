import json
import os
import urllib.request
import urllib.error

import boto3
from botocore.exceptions import ClientError

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


def _parse_body(event):
    body = event.get("body")
    if not body:
        return {}
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    bucket_name = os.environ.get("S3_BUCKET_NAME")
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")

    if not bucket_name:
        return _error(500, "S3_BUCKET_NAME environment variable is not set.")
    if not api_key:
        return _error(500, "ASSEMBLYAI_API_KEY environment variable is not set.")

    body = _parse_body(event)
    file_key = body.get("fileKey")

    if not file_key:
        return _error(400, "fileKey is required.")
    if not str(file_key).startswith("uploads/"):
        return _error(400, 'fileKey must start with "uploads/".')

    s3_client = boto3.client("s3")
    try:
        presigned_get_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": file_key},
            ExpiresIn=3600,
        )
    except ClientError as e:
        message = (
            "Failed to generate presigned GET URL. Check IAM permissions for s3:GetObject "
            f"on bucket {bucket_name}. Details: {str(e)}"
        )
        return _error(500, message)

    assembly_url = "https://api.assemblyai.com/v2/transcript"
    payload = {
        "audio_url": presigned_get_url,
        "language_detection": True,
        "punctuate": True,
        "format_text": True,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        assembly_url,
        data=data,
        headers={
            "authorization": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = str(e)
        message = f"AssemblyAI HTTP error {e.code}: {error_body}"
        return _error(502, message)
    except urllib.error.URLError as e:
        return _error(502, f"Error connecting to AssemblyAI: {e.reason}")

    transcript_id = resp_json.get("id")
    status = resp_json.get("status")

    if not transcript_id:
        return _error(
            502,
            "AssemblyAI response did not include an id. Check your request and API key.",
        )

    response_body = {
        "transcriptId": transcript_id,
        "status": status,
    }

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_body),
    }

