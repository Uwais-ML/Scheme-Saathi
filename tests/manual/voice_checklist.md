# Phase 24 Voice Upgrades: Manual Verification Checklist

Test this on a desktop browser and on a mobile / phone-sized browser viewport.
**Recommended:** Use headphones during testing to avoid microphone acoustic echo loops.

---

## 1. Mic Button During Playback
- [ ] **Action:** Start conversation and trigger a long spoken response from the agent.
- [ ] **Action:** While the TTS audio is actively playing, press the mic button.
- [ ] **Expected:**
  - Audio playback immediately stops.
  - Only after the button press, microphone access is requested and recording starts.
- [ ] **Action:** Reload the app without pressing the mic button.
- [ ] **Expected:** The app does not request microphone access during startup or TTS playback.

---

## 2. Silence Handling
- [ ] **Action:** Start recording without speaking, or pause speaking.
- [ ] **Expected (Auto-stop):** Recording automatically stops after 1.5 seconds of silence once speech was initiated.
- [ ] **Action:** Let the agent complete its response and do not speak for 8 seconds.
- [ ] **Expected (Gentle Prompt):** The agent plays one single gentle prompt: *"Are you there? Take your time."* / *"क्या आप सुन रहे हैं? आराम से बोलिए।"*
- [ ] **Expected (No Infinite Loops):** The agent does **not** loop the silence prompt repeatedly; it remains quiet until the user speaks.

---

## 3. Voice Controls (Deterministic Matching)
- [ ] **Action:** Say "फिर से बोलो" or "repeat".
- [ ] **Expected:** Agent replays the previous spoken response from the local audio cache without calling the LLM.
- [ ] **Action:** Say "धीमे बोलो" or "slower".
- [ ] **Expected:** Audio playback rate decreases (e.g., 0.8x) and persists for subsequent audio in the session.
- [ ] **Action:** Say "तेज़ बोलो" or "faster".
- [ ] **Expected:** Audio playback rate increases (e.g., 1.2x) and persists.
- [ ] **Action:** Say "रुको" or "stop".
- [ ] **Expected:** Immediate playback halt.
- [ ] **Action:** Say "वापस जाएं" or "go back".
- [ ] **Expected:** Navigates back or resets current form step.

---

## 4. Entity Confirmation
- [ ] **Action:** Provide an Aadhaar or phone number verbally (e.g. "मेरा मोबाइल नंबर 9876543210 है").
- [ ] **Expected:** Agent reads back the grouped digits ("क्या आपका नंबर नौ आठ सात छह पाँच, चार तीन दो एक शून्य है?") and asks for confirmation.
- [ ] **Action:** Say "हाँ" or "yes".
- [ ] **Expected:** Entity is locked in profile.
- [ ] **Action:** Say "नहीं" or "no".
- [ ] **Expected:** Agent asks user to state the number again.

---

## 5. TTS-Down Fallback
- [ ] **Action:** Disconnect network or set invalid TTS key.
- [ ] **Expected:** Visual text responses render gracefully in the UI chat window with zero application crashes, and cached fixed audio phrases (greetings, standing notices) continue to work.
