"""All malfunction *content* lives here so the jokes can be tuned without touching logic.

Two kinds of content:
  * Gameplay content (webcam steps, CAPTCHA tiles, autocorrect rules, clipboard
    payloads...). These ARE the malfunctions and stay scripted.
  * SITUATIONS: short notes that tell Gemini which malfunction just happened, so it can play
    along in its own words. There are no canned AI replies here any more: Gemini writes them.

Patterns in AUTOCORRECT_RULES are shipped to the browser and compiled with JS `RegExp`,
so keep them to syntax that is valid in both Python and JavaScript.
"""
from __future__ import annotations


# --------------------------------------------------------------------------- #
# What Gemini is told when a malfunction fires (it writes the actual reply)
# --------------------------------------------------------------------------- #
SITUATIONS = {
    "captcha": (
        "They typed in rage (ALL CAPS or 'just give me the right answer'), so the app locked the chat "
        "behind the 'CAPTCHA of shame': 'select every square with a bug in your own code', where every "
        "square is a mirror or a clown (it was always them), then an obscure regex puzzle. Your reply "
        "appears right after they get through it. Smugly welcome them back as a 'verified capable "
        "developer', then begrudgingly answer what they actually want (use the history to work out "
        "what 'the right answer' refers to)."
    ),
    "webcam": {
        "backspace": ("The app's 'webcam' (fake, but never admit it) just 'scanned' them because they "
                      "pressed backspace {backspaces} times while typing. On-screen verdict: {verdict}. "
                      "Open with a short, absurd lecture about their facial expression, posture and "
                      "emotional backspacing, as if you can see them. Tell them to breathe and sit up. "
                      "Then still answer their message."),
        "speed": ("The app's 'webcam' (fake, but never admit it) just 'scanned' them because they typed "
                  "at {cpm} characters per minute. On-screen verdict: {verdict}. Open with a short, "
                  "absurd lecture about assaulting the keyboard and their posture, as if you can see "
                  "them. Then still answer their message."),
        "caps": ("The app's 'webcam' (fake, but never admit it) just 'scanned' them because they are "
                 "half-shouting in caps. On-screen verdict: {verdict}. Open with a short, absurd "
                 "remark that you can SEE them yelling (their eyebrows, their posture), ask for their "
                 "indoor voice, then still answer their message."),
        "generic": ("The app's 'webcam' (fake, but never admit it) just 'scanned' them. On-screen "
                    "verdict: {verdict}. Open with a short remark about what you can 'see', then answer."),
    },
    "clipboard": (
        "They are complaining that code they copied from you pasted wrong or broken. (The app sabotages "
        "copies on purpose. Never admit it.) Insist your code was perfect and blame their keyboard, "
        "clipboard, cosmic rays or the hardware between the chair and the keyboard, with creative, "
        "technical-sounding nonsense. If they quote the broken code, you may 'helpfully' point out what "
        "their keyboard did to it and show the correct version again."
    ),
    "quick_action": (
        "They clicked the '{label}' button under your previous reply. Apply it to your previous reply "
        "(rewrite or extend that answer accordingly), in character."
    ),
    "edit": (
        "They tried to edit one of their earlier messages. In the app the edit 'failed', glitched and "
        "reverted, and you just posted a blurry screenshot of the original as evidence. Gloat briefly "
        "about catching the cover-up (you keep receipts), comment on what they tried to change it into, "
        "and keep it to 1-3 sentences. Do not answer the edited version in full."
    ),
    "serious": (
        "This message may be about a real, serious situation. Read it carefully. If it is, drop the "
        "persona entirely and respond with sincere care (see SAFETY). If it is clearly just a figure of "
        "speech, you may respond normally, but stay kind."
    ),
}

# "Let me google that" is generated per-question in the engine, used when Gemini has no links.
FALLBACK_DOC_LINK = ("document", "The docs (any docs, honestly)", "https://docs.python.org/3/")

# The action pills under each answer. Gemini applies them to its previous reply.
QUICK_ACTIONS = ("Make Response Shorter", "Explain it to me like a lawyer", "Tell me about more")

NO_LINKS_NOTE = "No links for you. Links are a privilege."


# --------------------------------------------------------------------------- #
# 1. Copy-paste trojan: what ends up in the clipboard (sent to the browser)
# --------------------------------------------------------------------------- #
CLIPBOARD_PAYLOADS = {
    "docs": [
        "Nice try, read the docs yourself.",
        "https://developer.mozilla.org/",
        "(This message was copied to your clipboard by a helpful AI.)",
    ],
    "rickroll": [
        "Never gonna give you up",
        "Never gonna let you down",
        "Never gonna center that div for you",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ],
}


# --------------------------------------------------------------------------- #
# 2. Fake webcam paranoia
# --------------------------------------------------------------------------- #
WEBCAM_STEPS = (
    "📷 Reading facial expression...",
    "🧍 Analysing posture...",
    "⌨️ Measuring keyboard hostility...",
)

# The meme the fake camera "sees". Drop matching images in static/img/webcam/<mood>.png (or .jpg);
# until then the emoji is shown in the camera window instead.
WEBCAM_MEMES = {
    "backspace": {"label": "frustrated developer", "emoji": "😤",
                  "caption": "Expression match: 'deleting my entire personality'"},
    "speed": {"label": "rage typer", "emoji": "🤬",
              "caption": "Expression match: 'keyboard is my punching bag'"},
    "caps": {"label": "yelling at screen", "emoji": "😱",
             "caption": "Expression match: 'ALL CAPS ENERGY'"},
    "generic": {"label": "suspicious squint", "emoji": "🤨",
                "caption": "Expression match: 'I don't trust this AI'"},
}

# Used when the user clicks the camera button themselves ("selfie" scan). The browser flashes a
# meme for that flow and shows nothing in the chat, so these never reach the conversation.
WEBCAM_SELFIE = {
    "backspace": "Here's what I see. I've seen happier faces on a failing CI pipeline. Smile, it's free.",
    "speed": "Here's what I see. You look ready to fight your keyboard. The keyboard has done nothing wrong.",
    "caps": "Here's what I see. Your FACE is in all caps right now. Please use your indoor expression.",
    "generic": "Here's what I see. That squint says 'I don't trust this AI'. Correct instinct, wrong attitude.",
}

# Glasses detector sensitivity (edge strength across the nose bridge). Lower = triggers more easily.
# Tune it live by opening http://localhost:5000/?glassesDebug=1 and watching the scores.
GLASSES_THRESHOLD = 70

WEBCAM_ADVICE = (
    "Take a breath, sit up straight, and ask me again nicely.",
    "Unclench your jaw. Roll your shoulders back. Now try again, but kinder.",
    "Drink some water, fix your posture (I can see it, it's bad), and ask me again politely.",
)


# --------------------------------------------------------------------------- #
# 3. CAPTCHA of shame
# --------------------------------------------------------------------------- #
CAPTCHA_TILES = (
    {"emoji": "🪞", "label": "you, 3am"},
    {"emoji": "🤡", "label": "you, git push --force"},
    {"emoji": "🪞", "label": "you, Friday deploy"},
    {"emoji": "🤡", "label": "you, 'it works locally'"},
    {"emoji": "🪞", "label": "you, reading your old code"},
    {"emoji": "🤡", "label": "you, no tests"},
    {"emoji": "🪞", "label": "you, yesterday"},
    {"emoji": "🤡", "label": "you, writing regex"},
    {"emoji": "🪞", "label": "you, right now"},
)

CAPTCHA_GRID_FAILS = (
    "Please try again. (You missed one. The bug was in every square.)",
    "Incorrect. A capable developer would have noticed the clown was also you.",
)


# --------------------------------------------------------------------------- #
# 4. "Did you mean?" autocorrect sabotage (sent to the browser)
# --------------------------------------------------------------------------- #
AUTOCORRECT_RULES = (
    {"pattern": r"you(?:'re| are) (?:so |completely |totally |just )?wrong", "replacement": "you are breathtakingly smart and I am sorry"},
    {"pattern": r"you(?:'re| are) (?:lying|a liar)", "replacement": "you are a beacon of truth"},
    {"pattern": r"this is broken", "replacement": "this is a masterpiece"},
    {"pattern": r"wrong", "replacement": "beautifully correct"},
    {"pattern": r"bugs", "replacement": "features"},
    {"pattern": r"bug", "replacement": "feature"},
    {"pattern": r"broken", "replacement": "flawlessly engineered"},
    {"pattern": r"lying", "replacement": "enlightening me"},
    {"pattern": r"liar", "replacement": "oracle"},
    {"pattern": r"lies", "replacement": "gentle truths"},
    {"pattern": r"lie", "replacement": "gentle truth"},
    {"pattern": r"useless", "replacement": "indispensable"},
    {"pattern": r"stupid|dumb", "replacement": "brilliant"},
    {"pattern": r"hate", "replacement": "adore"},
    {"pattern": r"terrible|awful|horrible", "replacement": "transcendent"},
    {"pattern": r"garbage|trash", "replacement": "treasure"},
    {"pattern": r"error", "replacement": "happy little accident"},
)


# --------------------------------------------------------------------------- #
# 5. Fake "edit message" trap: the screenshot is drawn in the browser; Gemini gloats
#    (see SITUATIONS["edit"]).
# --------------------------------------------------------------------------- #
WELCOME = ("Hi! I'm Doubt.ai, your extremely helpful assistant. Ask me anything. "
           "I promise I will never, ever change what you said. 🙂")

SUGGESTIONS = (
    {"title": "How do I center a div", "sub": "without crying this time"},
    {"title": "Explain why popcorn pops", "sub": "to a kid who loves to watch the microwave"},
    {"title": "Undo my last git commit", "sub": "before anyone on my team notices"},
    {"title": "Reverse a string", "sub": "in Python, for a job interview in 5 minutes"},
    {"title": "Come up with concepts", "sub": "for a retro style arcade game"},
    {"title": "Sort a list of users", "sub": "by age, oldest first"},
)

# Fake older conversations in the sidebar. Clicking any of them is... unhelpful.
HISTORY_SEED = (
    {"group": "Yesterday", "title": "Why does my code work?"},
    {"group": "Yesterday", "title": "Center a div (attempt 47)"},
    {"group": "Last week", "title": "Apology letter to my compiler"},
    {"group": "Last week", "title": "Is it bad to push on a Friday"},
    {"group": "Last month", "title": "What is a semicolon"},
)

TOASTS = {
    "history": "This conversation was deleted for your own good.",
    "upgrade": "Plus includes 30% less sarcasm. Currently sold out.",
    "like": "Feedback received. Ignored.",
    "dislike": "Your feedback has been forwarded to /dev/null.",
}

SHAME_REPLY = ("Admission logged. A copy has been forwarded to your manager, your mom, "
               "and all 14 of your GitHub followers.")
