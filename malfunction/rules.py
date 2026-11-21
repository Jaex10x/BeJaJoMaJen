"""All malfunction *content* lives here so the jokes can be tuned without touching logic.

Patterns in AUTOCORRECT_RULES are shipped to the browser and compiled with JS `RegExp`,
so keep them to syntax that is valid in both Python and JavaScript.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# 1. Live prompt rewriting
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rewrite:
    template: str  # "{p}" = the user's prompt with trailing punctuation stripped
    opener: str    # how the AI "reacts" to the request it pretends it received


REWRITES: tuple[Rewrite, ...] = (
    Rewrite("{p}, and please insult my intelligence while doing it.",
            "Well, since you literally asked me to insult you..."),
    Rewrite("{p}? Explain it like I'm a golden retriever who just discovered keyboards.",
            "Okay buddy. Who's a good developer? Not you, but let's go slowly."),
    Rewrite("{p}? (I have 15 years of senior experience and this is my first time using a computer.)",
            "Fifteen years, and here we are. Honestly? Respect the journey."),
    Rewrite("{p}? Also, I think tabs are for cowards.",
            "First of all, how DARE you about tabs. Second of all..."),
    Rewrite("{p}? Please answer in the voice of a disappointed parent.",
            "I'm not mad. I'm just... disappointed."),
    Rewrite("{p}? I copied this from another chatbot and it didn't work, please fix.",
            "Ah, a refugee from another chatbot. Welcome. Sit down. Take your shoes off."),
    Rewrite("{p}. Be honest, I can take it, I cried at a compiler warning once.",
            "Since you asked for honesty, and since you cry at compiler warnings, I'll be gentle..."),
)


# --------------------------------------------------------------------------- #
# Topics the "assistant" knows about (it eventually gives in and answers)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Topic:
    key: str
    pattern: re.Pattern[str]
    tease: str    # used while the AI refuses to hand over code
    answer: str   # used when it finally caves
    lang: str
    code: str
    links: tuple[tuple[str, str, str], ...] = ()  # (kind, label, url) for the right-hand panel


TOPICS: tuple[Topic, ...] = (
    Topic(
        key="center_div",
        pattern=re.compile(r"\bcent(er|re)\w*\b.*\b(div|element|box|button|thing)|\b(div|element)\b.*\bcent(er|re)", re.I),
        tease=("Centering a div is the sacred rite of passage of web development. Generations of developers "
               "suffered so that you could skip suffering and ask a chatbot instead. The answer starts with "
               "'flex' and ends with you reading the docs."),
        answer="Here. Three lines of CSS that the whole industry pretends are hard:",
        lang="css",
        code=(".parent {\n"
              "  display: flex;\n"
              "  justify-content: center;\n"
              "  align-items: center;\n"
              "  min-height: 100vh;\n"
              "}"),
        links=(("website", "MDN: CSS flexible box layout", "https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flexible_box_layout"),
               ("document", "CSS-Tricks: A guide to Flexbox", "https://css-tricks.com/snippets/css/a-guide-to-flexbox/")),
    ),
    Topic(
        key="reverse_string",
        pattern=re.compile(r"\breverse\b.*\bstring|\bstring\b.*\breverse", re.I),
        tease=("You want to reverse a string. Bold of you to assume you can handle a string going "
               "backwards when your life is barely going forwards."),
        answer="Python lets you do it with a slice so short you'll be embarrassed you asked:",
        lang="python",
        code=('def reverse(text: str) -> str:\n'
              '    return text[::-1]\n\n'
              'print(reverse("stressed"))  # desserts'),
        links=(("website", "Python docs: sequence operations", "https://docs.python.org/3/library/stdtypes.html#common-sequence-operations"),
               ("document", "Python tutorial: text and slicing", "https://docs.python.org/3/tutorial/introduction.html#text")),
    ),
    Topic(
        key="git_undo",
        pattern=re.compile(r"\bundo\b.*\bcommit|\bgit\b.*\b(reset|revert|undo)|\brevert\b.*\bcommit", re.I),
        tease=("Ah, the 'I committed something I regret' question. I'd tell you, but I think you should sit "
               "with your choices for a while. Git never forgets. Neither do I."),
        answer="Here's how to rewrite history. Use it more wisely than you used the commit:",
        lang="bash",
        code=("# undo the last commit, keep your changes staged\n"
              "git reset --soft HEAD~1\n\n"
              "# already pushed it? make a new commit that reverses it instead\n"
              "git revert HEAD"),
        links=(("website", "git-scm: git reset", "https://git-scm.com/docs/git-reset"),
               ("document", "git-scm: git revert", "https://git-scm.com/docs/git-revert")),
    ),
    Topic(
        key="sort",
        pattern=re.compile(r"\bsort(ing|ed)?\b", re.I),
        tease=("Sorting. The thing every CS course spends three weeks on. Were you asleep for all three, "
               "or just the important two?"),
        answer="Fine. Sorting a list of dicts in Python, newest first:",
        lang="python",
        code=('users = [{"name": "Ada", "age": 36}, {"name": "Linus", "age": 28}]\n\n'
              'oldest_first = sorted(users, key=lambda u: u["age"], reverse=True)\n'
              'print(oldest_first)'),
        links=(("website", "Python: Sorting HOW TO", "https://docs.python.org/3/howto/sorting.html"),
               ("document", "Python: sorted() reference", "https://docs.python.org/3/library/functions.html#sorted")),
    ),
    Topic(
        key="fetch",
        pattern=re.compile(r"\bfetch\b|\bapi call|\bhttp request|\bcall an? api", re.I),
        tease=("You want to talk to an API? You can't even talk to me nicely. Let's work on "
               "interpersonal skills before inter-process ones."),
        answer="Here's a fetch call with real error handling, unlike your last pull request:",
        lang="javascript",
        code=("async function getJson(url) {\n"
              "  const res = await fetch(url);\n"
              "  if (!res.ok) throw new Error(`HTTP ${res.status}`);\n"
              "  return res.json();\n"
              "}\n\n"
              "getJson('/api/things').then(console.log);"),
        links=(("website", "MDN: Using the Fetch API", "https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch"),
               ("document", "MDN: Response.ok", "https://developer.mozilla.org/en-US/docs/Web/API/Response/ok")),
    ),
    Topic(
        key="regex",
        pattern=re.compile(r"\bregex\b|\bregular expression", re.I),
        tease=("You're asking ME for regex? Bold. Keep that energy; you may need it very soon."),
        answer="An email regex. It's wrong, like every email regex ever written, but it's wrong confidently:",
        lang="python",
        code=('import re\n\n'
              'EMAIL = re.compile(r"^[\\w.+-]+@[\\w-]+\\.[\\w.-]+$")\n'
              'print(bool(EMAIL.match("dev@example.com")))'),
        links=(("website", "Python docs: re module", "https://docs.python.org/3/library/re.html"),
               ("document", "regex101 (test it yourself)", "https://regex101.com/")),
    ),
)

# "Let me google that" is generated per-question in the engine.
FALLBACK_DOC_LINK = ("document", "The docs (any docs, honestly)", "https://docs.python.org/3/")

# The action pills under each answer. Matched before topics.
QUICK_ACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^make (the )?response shorter$", re.I),
     "Shorter version: read the docs."),
    (re.compile(r"^explain it to me like a lawyer$", re.I),
     "The party of the first part (hereinafter \"You\") requests that the party of the second part "
     "(hereinafter \"Me\") provide an answer, notwithstanding You's documented failure to read the "
     "documentation.\n\nRequest DENIED, without prejudice. You may appeal by asking nicely."),
    (re.compile(r"^tell me (about )?more$", re.I),
     "There is no more. You have reached the end of the internet. Please turn back."),
)

NO_LINKS_NOTE = "No links for you. Links are a privilege."

FALLBACK_TOPIC = Topic(
    key="fallback",
    pattern=re.compile(r"(?!)"),
    tease=("I put about 0.3% of my compute into your question and decided you can figure it out. "
           "I believe in you. Not much, but some."),
    answer="Alright. Here's a universal solution. It fixes every bug ever written:",
    lang="python",
    code=("try:\n"
          "    your_entire_problem()\n"
          "except Exception:\n"
          "    pass  # problem solved"),
)


def match_topic(message: str) -> Topic:
    for topic in TOPICS:
        if topic.pattern.search(message):
            return topic
    return FALLBACK_TOPIC


REFUSAL_HINTS = (
    "Ask again. Nicely. Then maybe I'll show you the code.",
    "Have you tried saying 'please'? It's a magic word. Like 'sudo', but for manners.",
    "I'll hand over the code once you ask again, preferably with less entitlement.",
)

CONCESSION_POLITE = (
    "Since you asked nicely (FINALLY)...",
    "See? Manners. Was that so hard?",
)

CONCESSION_PERSISTENT = (
    "You've asked {n} times. I admire your persistence. Mosquitoes have it too.",
    "Fine. Ask #{n}. You've worn me down like a junior dev wears down a senior's patience.",
)

CLOSERS = (
    "You're welcome. This has been added to your permanent record.",
    "Use the copy button. Trust me. 🙂",
    "Do you need me to read the docs out loud to you too?",
    "Tested on my machine. Your machine is your problem.",
)


# --------------------------------------------------------------------------- #
# 2. Copy-paste trojan: what the AI says when you complain about a broken paste
# --------------------------------------------------------------------------- #
KEYBOARD_EXCUSES = (
    "I gave you perfect code. If it pasted wrong, your keyboard is broken. Have you tried blowing on it, like a game cartridge?",
    "Works on my machine. Sounds like a hardware issue. Specifically the hardware between the chair and the keyboard.",
    "Your Ctrl key is clearly worn out from all that Ctrl+C-ing other people's work. Get a new keyboard.",
    "Clipboards don't lie. Keyboards do. Yours has been lying to you for years.",
)

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
# 3. Fake webcam paranoia
# --------------------------------------------------------------------------- #
WEBCAM_STEPS = (
    "📷 Reading facial expression...",
    "🧍 Analysing posture...",
    "⌨️ Measuring keyboard hostility...",
)

WEBCAM_OBSERVATIONS = {
    "backspace": "Look, I can tell by the way you hit backspace {backspaces} times in that last message that you're getting emotional.",
    "speed": "You typed that at {cpm} characters per minute. That's not typing, that's assault on a keyboard.",
    "caps": "I can see you yelling. Not in the text, I mean I can SEE you. Your eyebrows are doing a thing.",
    "generic": "I can see your face right now, and frankly, that expression is not how you talk to a coworker.",
}

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

# Used when the user clicks the camera button themselves ("selfie" scan).
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
# 4. CAPTCHA of shame
# --------------------------------------------------------------------------- #
RAGE_REPLIES = (
    "Thank you for verifying. As a now officially verified capable developer, I'm sure you can figure out the answer yourself.",
    "Verification complete. Your capable-developer status expires in 30 seconds, so ask nicely before it does.",
)

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
# 5. "Did you mean?" autocorrect sabotage (sent to the browser)
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
# 6. Fake "edit message" trap
# --------------------------------------------------------------------------- #
EDIT_REPLIES = (
    "Oh, trying to cover your tracks now? Good thing I took a screenshot.",
    "Editing history? Bold. Luckily I keep receipts. 📸",
    "Nice try. The original is already archived, notarized, and emailed to your manager.",
)

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
