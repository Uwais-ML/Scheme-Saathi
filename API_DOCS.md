# Scheme Saathi – API Reference Documentation

The Scheme Saathi backend is built with FastAPI. All endpoints are prefixed with `/api` unless serving root health checks or static web assets.

---

## 1. Session & Chat Endpoints

### `POST /api/session`
Create a new agent session or resume an existing session for a user.

- **Request Body** (`application/json`):
  ```json
  {
    "user_id": "optional_string",
    "language": "hi" // "hi" | "en" | "mr" | "ta"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "greeting": "नमस्ते! मैं आपका योजना साथी हूँ...",
    "language": "hi"
  }
  ```

---

### `POST /api/chat`
Execute a conversational turn with the Scheme Saathi agent loop.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "text": "क्या मेरे लिए कोई किसान योजना है?",
    "upload_ids": []
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "messages": [
      "सुरक्षा सूचना: सरकारी योजनाओं के लिए आवेदन निशुल्क होता है। किसी को पैसे या अपना OTP कभी न दें।",
      "मैं आपके लिए किसान योजनाओं की तलाश कर रहा हूँ..."
    ],
    "checklist": {
      "total": 3,
      "documents": [
        { "doc_id": "aadhaar", "status": "verified" },
        { "doc_id": "bank_passbook", "status": "waiting" }
      ]
    },
    "form_preview": {
      "scheme_id": "pm_kisan",
      "provisional": true,
      "fields": [
        { "key": "farmer_name", "label": "किसान का नाम", "value": "रामेश कुमार" }
      ]
    },
    "member": {
      "active_member_id": "mem_101",
      "active_name": "रामेश कुमार",
      "active_relation": "self",
      "members": [
        { "member_id": "mem_101", "display_name": "रामेश कुमार", "relation": "self", "is_active": true }
      ]
    },
    "notices": []
  }
  ```

---

## 2. Voice Endpoints

### `POST /api/stt`
Transcribe audio from the microphone into text via AssemblyAI.

- **Request** (`multipart/form-data`):
  - `file`: Audio file (`.webm`, `.wav`, `.ogg`)
  - `language`: `"hi"`, `"en"`, etc.
  - `session_id`: Optional string
- **Response** (`200 OK`):
  ```json
  {
    "text": "मेरी उम्र चालीस साल है",
    "confidence": 0.95
  }
  ```

---

### `POST /api/tts`
Synthesize text into natural WAV audio stream via Cartesia Sonic API.

- **Request Body** (`application/json`):
  ```json
  {
    "text": "प्रधानमंत्री किसान सम्मान निधि योजना में हर साल 6000 रुपये मिलते हैं।",
    "language": "hi"
  }
  ```
- **Response** (`200 OK`):
  - `Content-Type`: `audio/wav`
  - Raw binary WAV PCM audio stream formatted with digit pauses and natural currency pronunciation.

---

### `POST /api/voice_command`
Fast deterministic voice control and entity yes/no matcher (bypasses LLM).

- **Request Body** (`application/json`):
  ```json
  {
    "text": "थोड़ा धीरे बोलो",
    "language": "hi"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "command": "slower", // "repeat" | "slower" | "faster" | "stop" | "wait" | "go back" | null
    "is_confirmation": null // true (yes) | false (no) | null (unclear)
  }
  ```

---

## 3. Household Management Endpoints

### `GET /api/household`
Retrieve complete household hierarchy, members, and consent logs.

- **Query Parameters**:
  - `session_id` (string, required)
- **Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "household_id": "user_a1b2c3d4",
    "active_member_id": "mem_101",
    "members": [
      {
        "member_id": "mem_101",
        "display_name": "रामेश",
        "relation": "self",
        "is_active": true,
        "profile": { "is_farmer": true, "land_holding": 2.5 }
      },
      {
        "member_id": "mem_102",
        "display_name": "सुनीता",
        "relation": "spouse",
        "is_active": false,
        "profile": { "gender": "female", "age": 35 }
      }
    ]
  }
  ```

---

### `POST /api/household/member`
Add a new family member to the household and log consent.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "relationship": "spouse",
    "name": "सुनीता",
    "age": 35,
    "gender": "female"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "member_id": "mem_102",
    "display_name": "सुनीता",
    "relation": "spouse",
    "consent_prompt": "मैंने सुनीता (spouse) को परिवार में जोड़ लिया है..."
  }
  ```

---

### `POST /api/household/switch`
Switch the active household member who the agent is assisting.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "member_id": "mem_102"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "active_member_id": "mem_102",
    "message": "अब हम सुनीता की सहायता कर रहे हैं।"
  }
  ```

---

## 4. Offline Handoff & Grievance Endpoints

### `POST /api/handoff/packet`
Generate a clean, printable HTML/PDF handoff summary for CSC or Panchayat visit.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "reason": "Missing bank land record and need offline verification",
    "district": "bhopal"
  }
  ```
- **Response** (`200 OK`):
  - `Content-Type`: `text/html`
  - Printable HTML document listing verified documents, pending requirements, and local office contact.

---

### `POST /api/grievance/draft`
Generate a formal grievance appeal letter based on application rejection.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "scheme_id": "pm_kisan",
    "rejection_category": "name_mismatch",
    "user_facts": {
      "reference_number": "PMK-2024-9876",
      "issue_details": "आधार और खतौनी में नाम की वर्तनी में अंतर था जो सुधार लिया गया है"
    }
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "letter": "सेवा में,\nश्रीमान जन शिकायत निवारण अधिकारी...\n\nविषय: PM-KISAN आवेदन (क्रमांक: PMK-2024-9876)...",
    "category": "name_mismatch",
    "portal": "https://pgportal.gov.in"
  }
  ```

---

## 5. Form & Document Upload Endpoints

### `POST /api/upload`
Upload a document image or PDF for VLM extraction and field mapping.

- **Request** (`multipart/form-data`):
  - `file`: Image/PDF file
  - `session_id`: Session ID string
  - `doc_type`: e.g. `"aadhaar"`, `"ration_card"`, `"bank_passbook"`
- **Response** (`200 OK`):
  ```json
  {
    "upload_id": "upl_9f8e7d",
    "filename": "aadhaar_front.jpg",
    "size_bytes": 1048576
  }
  ```

---

### `GET /api/form/preview/{scheme_id}`
Retrieve the current form filling draft and extracted fields.

- **Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "data": {
      "scheme_id": "pm_kisan",
      "provisional": true,
      "fields": [...]
    }
  }
  ```

---

### `POST /api/form/confirm`
User explicitly confirms that draft form data is correct.

- **Request Body** (`application/json`):
  ```json
  {
    "session_id": "user_a1b2c3d4",
    "scheme_id": "pm_kisan",
    "confirmed": true
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "status": "confirmed",
    "message": "फ़ॉर्म की जानकारी सफलतापूर्वक सत्यापित हो गई है।"
  }
  ```
