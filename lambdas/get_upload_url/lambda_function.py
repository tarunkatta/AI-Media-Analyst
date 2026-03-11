import json
import os
import uuid

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
  if not bucket_name:
      return _error(500, "S3_BUCKET_NAME environment variable is not set.")

  body = _parse_body(event)
  filename = body.get("filename")
  content_type = body.get("contentType") or "audio/mpeg"

  if not filename:
      return _error(400, "filename is required.")

  dot_index = filename.rfind(".")
  ext = filename[dot_index:].lower() if dot_index != -1 else ""

  allowed_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
  if ext not in allowed_exts:
      return _error(
          400,
          "Unsupported file extension. Allowed: .mp3, .wav, .m4a, .ogg, .flac, .webm, .mp4",
      )

  file_key = f"uploads/{uuid.uuid4()}{ext}"

  s3_client = boto3.client("s3")

  try:
      upload_url = s3_client.generate_presigned_url(
          ClientMethod="put_object",
          Params={
              "Bucket": bucket_name,
              "Key": file_key,
              "ContentType": content_type,
          },
          ExpiresIn=300,
      )
  except ClientError as e:
      message = (
          "Failed to generate presigned URL. Check IAM permissions for s3:PutObject "
          f"on bucket {bucket_name}. Details: {str(e)}"
      )
      return _error(500, message)

  response_body = {
      "uploadUrl": upload_url,
      "fileKey": file_key,
      "contentType": content_type,
  }

  return {
      "statusCode": 200,
      "headers": CORS_HEADERS,
      "body": json.dumps(response_body),
  }

