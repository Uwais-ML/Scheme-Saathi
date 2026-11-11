"""Pre-written fallback messages for graceful degradation in multiple languages."""

FALLBACK_MESSAGES: dict[str, dict[str, str]] = {
    "main_llm_down": {
        "hi": "क्षमा करें, मुझे इस समय तकनीकी समस्या आ रही है। कृपया कुछ मिनट बाद दोबारा प्रयास करें।",
        "en": "Sorry, I am having trouble right now. Please try again in a few minutes.",
        "mr": "क्षमस्व, मला सध्या तांत्रिक समस्या येत आहे. कृपया काही मिनिटांनंतर पुन्हा प्रयत्न करा.",
        "ta": "மன்னிக்கவும், இப்போது தொழில்நுட்ப சிக்கல் உள்ளது. சில நிமிடங்கள் கழித்து மீண்டும் முயற்சிக்கவும்.",
    },
    "vlm_unverified": {
        "hi": "दस्तावेज की स्वचालित जांच पूरी नहीं हो सकी। कृपया मुख्य विवरण बोलकर पुष्टि करें।",
        "en": "Automated document verification is currently unavailable. Please confirm key details aloud.",
        "mr": "दस्तऐवजांची स्वयंचलित पडताळणी होऊ शकली नाही. कृपया मुख्य तपशील बोलून निश्चित करा.",
        "ta": "ஆவண சரிபார்ப்பு கிடைக்கவில்லை. முக்கிய விவரங்களை உறுதிப்படுத்தவும்.",
    },
    "stt_fallback": {
        "hi": "आवाज़ पहचानने में समस्या हो रही है, कृपया लिखकर बताएं।",
        "en": "Voice recognition is not available right now. Please type your message.",
        "mr": "आवाज ओळखण्यात अडचण येत आहे, कृपया टाईप करा.",
        "ta": "குரல் அங்கீகாரத்தில் சிக்கல் உள்ளது, தயவுசெய்து தட்டச்சு செய்யவும்.",
    },
    "tts_fallback": {
        "hi": "ऑडियो प्लेबैक उपलब्ध नहीं है, संदेश स्क्रीन पर दिखाया जा रहा है।",
        "en": "Audio playback is unavailable. Displaying message on screen.",
        "mr": "ऑडिओ उपलब्ध नाही, संदेश स्क्रीनवर दाखवला जात आहे.",
        "ta": "ஆடியோ கிடைக்கவில்லை, திரையில் செய்தி காட்டப்படுகிறது.",
    },
    "search_down": {
        "hi": "लाइव वेब खोज अभी उपलब्ध नहीं है, मैं संग्रहीत जानकारी से उत्तर दे रहा हूँ।",
        "en": "Live web search is unavailable. Answering from local database only.",
        "mr": "थेट वेब शोध उपलब्ध नाही, स्थानिक माहितीवरून उत्तर देत आहे.",
        "ta": "வலை தேடல் கிடைக்கவில்லை, உள்ளூர் தகவல்களிலிருந்து பதிலளிக்கிறேன்.",
    },
    "guardrail_violation": {
        "hi": "आप इस योजना के लिए पात्र प्रतीत होते हैं। कृपया ध्यान दें कि अंतिम निर्णय संबंधित सरकारी कार्यालय द्वारा लिया जाता है और आवेदन निशुल्क होता है।",
        "en": "You appear to be eligible for this scheme. Please note that the final decision is made by the government office, and applications are free.",
        "mr": "आपण या योजनेसाठी पात्र दिसत आहात. अंतिम निर्णय संबंधित सरकारी कार्यालयाचा असतो आणि अर्ज मोफत असतो.",
        "ta": "நீங்கள் இந்த திட்டத்திற்கு தகுதியுடையவராகத் தோன்றுகிறீர்கள். இறுதி முடிவு அரசு அலுவலகத்தால் எடுக்கப்படுகிறது.",
    },
}


def get_fallback_message(reason: str, lang: str = "hi") -> str:
    """Return friendly pre-written fallback message in user's language."""
    catalog = FALLBACK_MESSAGES.get(reason, FALLBACK_MESSAGES["main_llm_down"])
    return catalog.get(lang, catalog.get("hi", "कृपया कुछ समय बाद पुनः प्रयास करें।"))
