# Audio Transcribe

Audio Transcribe is a full-stack web app that lets you upload audio files and get accurate, formatted transcripts using AssemblyAI. Files are uploaded directly from the browser to your own S3 bucket via a presigned URL, and three AWS Lambda functions coordinate the upload and transcription flow.

---

## How it works — end‑to‑end data flow

1. **Get presigned upload URL**
   - The frontend calls the `get_upload_url` Lambda (`/get-upload-url` API Gateway endpoint).
   - The Lambda validates the filename and generates a short‑lived presigned **PUT** URL for your S3 bucket.
   - The Lambda returns `{ uploadUrl, fileKey, contentType }` to the browser.

2. **Upload file directly to S3**
   - The browser uses the presigned `uploadUrl` to `PUT` the audio file directly to S3 (no backend proxy).
   - Upload progress is tracked client‑side using `XMLHttpRequest` upload events and shown in the UI.
   - Once the upload finishes, the frontend holds on to the `fileKey` that identifies the object in S3.

3. **Start transcription with AssemblyAI**
   - The frontend calls the `start_transcription` Lambda (`/start-transcription`) with `{ fileKey }`.
   - The Lambda creates a presigned **GET** URL for the uploaded audio object so AssemblyAI can download it.
   - The Lambda POSTs to AssemblyAI’s `/v2/transcript` API with the presigned URL and options (language detection, punctuation, formatted text).
   - AssemblyAI responds with a `transcriptId` and an initial `status` (usually `queued` or `processing`), which the Lambda returns to the frontend.

4. **Poll transcript status**
   - The frontend repeatedly calls the `get_transcript` Lambda (`/get-transcript?id={transcriptId}`) every 3 seconds.
   - The Lambda GETs `https://api.assemblyai.com/v2/transcript/{id}` and returns a simplified JSON payload.
   - Polling stops when:
     - `status === "completed"` (success) or
     - `status === "error"` (failure) or
     - The client hits the maximum number of polling attempts.

5. **Display transcript**
   - When `status === "completed"`, the frontend shows:
     - The full transcript text
     - Confidence score
     - Audio duration (seconds)
     - Optional word‑level detail
   - Users can copy the transcript to the clipboard or start a new upload.

---

## Tech stack

- **Frontend**: React 18 + Vite
- **Auth**: Firebase Authentication (Google Sign‑In)
- **Storage**: AWS S3 (direct browser uploads via presigned PUT URLs)
- **Backend**: 3 AWS Lambda functions (Python 3.12) behind an API Gateway REST API
- **Transcription**: AssemblyAI async transcription API
- **Deployment**: Vercel (frontend), AWS Lambda + API Gateway (backend)

---

## Local development

### 1. Clone and install frontend dependencies

```bash
cd audio-transcribe/frontend
npm install
```

### 2. Create your `.env` file

In the project root (`audio-transcribe/`):

1. Copy the example file:

```bash
cp .env.example .env
```

2. Fill in all the `VITE_*` values from:
   - **API Gateway Invoke URL** (AWS Console → API Gateway → your API → Stages → `prod` → Invoke URL)
   - **Firebase Web App config** (Firebase Console → Project Settings → Your Apps → Web App → `firebaseConfig`)

> **Note:** Vite automatically exposes `VITE_*` variables to the frontend via `import.meta.env`.

### 3. Run the dev server

From `audio-transcribe/frontend`:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

Log in with Google, upload an audio file, and watch the progress and transcription status in real time.

---

## Backend setup (AWS)

You will deploy three Python 3.12 Lambda functions and connect them to an API Gateway REST API:

- `get_upload_url` → `POST /get-upload-url`
- `start_transcription` → `POST /start-transcription`
- `get_transcript` → `GET /get-transcript`

### 1. Create an S3 bucket

1. In the AWS Console, open **S3** and create a new bucket (e.g. `YOUR_S3_BUCKET_NAME_HERE`).
2. Enable appropriate CORS for presigned PUT uploads, including:
   - `AllowedMethods`: `GET`, `PUT`, `HEAD`
   - `AllowedOrigins`: your frontend origin(s) (e.g. `http://localhost:5173`, your Vercel domain)
   - `AllowedHeaders`: `*` or at least `Content-Type`, `Authorization`

### 2. Create the Lambda functions

For each Lambda (`get_upload_url`, `start_transcription`, `get_transcript`):

1. Create a new Lambda function (Python 3.12 runtime).
2. Upload the corresponding `lambda_function.py` from the `lambdas/` folder.
3. Set the **handler** to `lambda_function.lambda_handler`.
4. Configure **environment variables**:
   - `S3_BUCKET_NAME` (for `get_upload_url` and `start_transcription`)
   - `ASSEMBLYAI_API_KEY` (for `start_transcription` and `get_transcript`)
5. Make sure the Lambda execution role has:
   - `s3:PutObject` and `s3:GetObject` permissions for your bucket
   - Basic CloudWatch Logs permissions

### 3. Create an API Gateway REST API

1. In **API Gateway**, create a new REST API.
2. For each route:
   - `POST /get-upload-url` → integrate with `get_upload_url` Lambda (proxy integration).
   - `POST /start-transcription` → integrate with `start_transcription` Lambda.
   - `GET /get-transcript` → integrate with `get_transcript` Lambda.
3. Enable **CORS** for each method (OPTIONS support, `Access-Control-Allow-Origin: *`).
4. Deploy to a stage (e.g. `prod`).
5. Copy the **Invoke URL** and set it as `VITE_API_BASE_URL` in your `.env`.

---

## Frontend deployment (Vercel)

1. Push this repository to GitHub/GitLab/Bitbucket.
2. In Vercel:
   - Create a new project from the `audio-transcribe/frontend` directory.
   - Build command: `npm run build`
   - Output directory: `dist`
3. Set the same environment variables used in local development:
   - `VITE_API_BASE_URL`
   - `VITE_FIREBASE_API_KEY`
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
4. Deploy, then add the Vercel domain to:
   - Firebase Authentication → `Authorized domains`
   - S3 Bucket CORS `AllowedOrigins`

---

## Backend deployment summary

- **Lambda**
  - Runtime: Python 3.12
  - No extra dependencies required (only `boto3`, `botocore`, `urllib`, and stdlib).
  - All functions return CORS headers on every response (including errors and OPTIONS).

- **API Gateway**
  - Routes:
    - `POST /get-upload-url`
    - `POST /start-transcription`
    - `GET /get-transcript`
  - CORS and `OPTIONS` methods enabled for browser access.

---

## Environment variables

Below is a reference for all environment variables used across the project.

| Name                             | Location                    | Description                                                                                     |
| -------------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL`             | Frontend `.env`            | Base URL for your API Gateway (e.g. `https://abc123.execute-api.region.amazonaws.com/prod`).   |
| `VITE_FIREBASE_API_KEY`         | Frontend `.env`            | Firebase Web App API key from `firebaseConfig`.                                                |
| `VITE_FIREBASE_AUTH_DOMAIN`     | Frontend `.env`            | Firebase auth domain (e.g. `your-project.firebaseapp.com`).                                    |
| `VITE_FIREBASE_PROJECT_ID`      | Frontend `.env`            | Firebase project ID.                                                                           |
| `VITE_FIREBASE_STORAGE_BUCKET`  | Frontend `.env`            | Firebase storage bucket (not used for S3, but part of `firebaseConfig`).                       |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Frontend `.env`        | Firebase messaging sender ID.                                                                  |
| `VITE_FIREBASE_APP_ID`          | Frontend `.env`            | Firebase web app ID.                                                                           |
| `S3_BUCKET_NAME`                | Lambda env vars            | Name of your S3 bucket that stores uploaded audio (used by `get_upload_url`, `start_transcription`). |
| `ASSEMBLYAI_API_KEY`            | Lambda env vars            | AssemblyAI API key for transcription (`start_transcription`, `get_transcript`).                |

Fill these values carefully before deploying or running the app in production.

---

## Security notes

- Never commit your real `.env` file to version control.
- Restrict your S3 bucket and IAM roles to the minimum required permissions.
- Keep your `ASSEMBLYAI_API_KEY` and Firebase credentials secret (only stored in env vars).
- Restrict Firebase Authentication to trusted domains (local dev + your production domains).

You now have everything you need to run Audio Transcribe locally and deploy it to production using Vercel and AWS. Enjoy building!

