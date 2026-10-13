"""
Big Brother Inc. - a pixel-art AI company made of local Ollama models.

You are Big Brother. Winston, your Chief of Staff, comes to your office -> he
hands the job to the right department on the office floor -> the Thought
Police interrogate the work -> Winston brings it to you -> you decide whether
it is released or sent back.

Runs on plain Python 3.10+ with no extra packages. Start it with
start_house.bat (or: python server.py) and it opens in your browser.
"""

import base64
import io
import json
import os
import zipfile
from html import unescape
import queue
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "housemates.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected")
RELEASED_DIR = os.path.join(BASE_DIR, "released")
FILES = {}                 # file id -> {"name", "text"}
MAX_FILE_CHARS = 20000     # how much of your files the housemates read


# ---------------------------------------------------------------- config

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()
SETTINGS = CONFIG["settings"]
HOUSEMATES = {h["id"]: h for h in CONFIG["housemates"]}
# ---------------------------------------------------------------- unpersons
# Anyone removed from housemates.json is "vaporised": remembered only as someone who never existed.
RECORDS_PATH = os.path.join(BASE_DIR, "records.json")
FORMER_CAST = [("Max", "Head of House"), ("Byte", "Developer"), ("Ada", "Tutor"), ("Sam", "Student"),
               ("Dex", "Entrepreneur"), ("Vera", "Sceptic"), ("Quinn", "Quality Director"), ("Cleo", "Clarity Director")]


def update_records():
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        records = {"staff": {}, "unpersons": [{"name": n, "role": r, "when": "before records began"} for n, r in FORMER_CAST]}
    current = {h["id"]: {"name": h["name"], "role": h["role"]} for h in CONFIG["housemates"]}
    for hid, old in records.get("staff", {}).items():
        if hid not in current or current[hid]["name"] != old["name"]:
            records["unpersons"].append({"name": old["name"], "role": old["role"], "when": time.strftime("%d %b")})
    records["staff"] = current
    try:
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception:
        pass
    return records["unpersons"]


HEAD_ID = "head"
BOARD = [hid for hid, h in HOUSEMATES.items() if h.get("board")]
UNPERSONS = update_records()
STAFF = [hid for hid in HOUSEMATES if hid != HEAD_ID and hid not in BOARD]


# ---------------------------------------------------------------- event bus
# The browser listens on /events (Server-Sent Events) and animates the office.

class EventBus:
    def __init__(self):
        self.lock = threading.Lock()
        self.subscribers = []
        self.diary_history = []          # replayed when a browser connects
        self.positions = {hid: "free" for hid in HOUSEMATES}

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def publish(self, event):
        with self.lock:
            if event["type"] == "move":
                self.positions[event["id"]] = event["room"]
            if event["type"] in ("diary", "vote", "council"):
                self.diary_history.append(event)
                self.diary_history = self.diary_history[-200:]
            for q in self.subscribers:
                q.put(event)


BUS = EventBus()


def move(hid, room):
    BUS.publish({"type": "move", "id": hid, "room": room})


def say(hid, text):
    text = " ".join(text.split())
    if len(text) > 90:
        text = text[:87].rstrip() + "..."
    BUS.publish({"type": "say", "id": hid, "text": text})


def diary(sender, text, kind="message", to=None):
    event = {"type": "diary", "from": sender, "text": text, "kind": kind}
    if to:
        event["to"] = to
    BUS.publish(event)


def status(text, working=None):
    BUS.publish({"type": "status", "text": text, "working": working})


# ---------------------------------------------------------------- ollama

INSTALLED_MODELS = set()
MODEL_FOR = {}            # housemate id -> model actually used


def refresh_models():
    """Ask Ollama which models are downloaded, and pick a working model for each housemate."""
    global INSTALLED_MODELS
    try:
        with urllib.request.urlopen(SETTINGS["ollama_url"] + "/api/tags", timeout=10) as r:
            data = json.load(r)
        INSTALLED_MODELS = {m["name"] for m in data.get("models", [])}
    except Exception:
        INSTALLED_MODELS = set()

    warnings = []
    default = SETTINGS["default_model"]
    for hid, h in HOUSEMATES.items():
        wanted = h.get("model", default)
        if model_installed(wanted):
            MODEL_FOR[hid] = wanted
        elif model_installed(default):
            MODEL_FOR[hid] = default
            warnings.append(f"{h['name']} wants {wanted}, which isn't downloaded, so is using {default} for now. "
                            f"Run: ollama pull {wanted}")
        else:
            MODEL_FOR[hid] = wanted
    return warnings


def model_installed(name):
    if not INSTALLED_MODELS:
        return False
    return name in INSTALLED_MODELS or (name + ":latest") in INSTALLED_MODELS


def ollama_chat(hid, system, user, json_mode=False, live=False):
    """Ask a housemate's model. With live=True the words stream onto their screen as they write."""
    body = {
        "model": MODEL_FOR.get(hid, SETTINGS["default_model"]),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": live,
        "options": {"num_ctx": SETTINGS.get("context_length", 8192)},
    }
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request(
        SETTINGS["ollama_url"] + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        if not live:
            data = json.load(r)
            return data.get("message", {}).get("content", "").strip()
        text, last = "", 0.0
        for raw in r:
            if not raw.strip():
                continue
            data = json.loads(raw)
            text += data.get("message", {}).get("content", "")
            if time.time() - last > 0.7 or data.get("done"):
                last = time.time()
                lines = [l.strip(" #*-`>") for l in text.splitlines() if l.strip(" #*-`>")]
                BUS.publish({"type": "progress", "id": hid, "words": len(text.split()),
                             "line": (lines[-1] if lines else "")[:90]})
            if data.get("done"):
                break
        return text.strip()


def parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}



# ---------------------------------------------------------------- files

TEXT_TYPES = (".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".css", ".java", ".c", ".cpp",
              ".ts", ".sql", ".xml", ".yaml", ".yml", ".rtf", ".tex")


def xml_text(xml, para_tag):
    xml = re.sub(rf"</{para_tag}>", "\n", xml)
    xml = re.sub(r"<w:tab/>|<a:tab/>", "\t", xml)
    return unescape(re.sub(r"<[^>]+>", "", xml))


def extract_text(name, raw):
    ext = os.path.splitext(name.lower())[1]
    if ext == ".docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return xml_text(z.read("word/document.xml").decode("utf-8"), "w:p").strip()
    if ext == ".pptx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                            key=lambda n: int(re.findall(r"\d+", n)[-1]))
            return "\n\n".join(f"[Slide {i + 1}]\n" + xml_text(z.read(n).decode("utf-8"), "a:p").strip()
                               for i, n in enumerate(slides))
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("reading PDFs needs the pypdf package. Close Big Brother and start it again "
                             "with start_house.bat, which installs it for you.")
        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join(f"[Page {i + 1}]\n" + (p.extract_text() or "") for i, p in enumerate(reader.pages)).strip()
    if ext in TEXT_TYPES or not ext:
        return raw.decode("utf-8", errors="replace")
    raise ValueError("Big Brother can read PDF, Word (.docx), PowerPoint (.pptx) and text/code files for now.")


def files_block(file_ids):
    """The text of attached files, as housemates see it."""
    parts, budget = [], MAX_FILE_CHARS
    for fid in file_ids:
        f = FILES.get(fid)
        if not f or budget <= 0:
            continue
        text = f["text"][:budget]
        cut = " (cut short, it was very long)" if len(text) < len(f["text"]) else ""
        parts.append(f"\n\n=== Attached file: {f['name']}{cut} ===\n{text}")
        budget -= len(text)
    return "".join(parts)


def summarise_files(file_ids):
    """Just names and opening lines, for the Head of House's planning."""
    lines = []
    for fid in file_ids:
        f = FILES.get(fid)
        if f:
            lines.append(f"- {f['name']}: starts with \"{' '.join(f['text'][:300].split())}\"")
    return ("\n\nBig Brother attached these files (the staff will see them in full):\n" + "\n".join(lines)) if lines else ""


# ---------------------------------------------------------------- the records department

def save_record(folder, task, body):
    os.makedirs(folder, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", task[:50].lower()).strip("-") or "work"
    name = time.strftime("%Y-%m-%d_%H%M%S_") + slug + ".md"
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(body)
    return name


def list_records():
    items = []
    for kind, folder in (("approved", RELEASED_DIR), ("rejected", REJECTED_DIR)):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.endswith(".md"):
                path = os.path.join(folder, name)
                with open(path, "r", encoding="utf-8") as f:
                    title = f.readline().lstrip("# ").strip()
                items.append({"kind": kind, "name": name, "title": title[:120], "when": os.path.getmtime(path)})
    return sorted(items, key=lambda x: -x["when"])


# ---------------------------------------------------------------- prompts

def persona(h):
    where = "in the Thought Police" if h.get("board") else f"in the {h.get('department', 'Executive')} department"
    return (f"You are {h['name']}, the {h['role']} {where} at Big Brother Inc., a company run by AI staff. "
            f"The user is Big Brother, who runs the company and decides what gets released. "
            f"Your personality: {h['personality']}")


def roster():
    lines = []
    for hid in STAFF:
        h = HOUSEMATES[hid]
        lines.append(f"- id \"{hid}\": {h['name']}, {h['role']} ({h.get('department', '')}). Skills: {h.get('skills', '')}")
    return "\n".join(lines)


def first_line(text):
    for line in text.splitlines():
        line = line.strip(" #*-`>")
        if len(line) > 3:
            return line
    return text[:80]


# ---------------------------------------------------------------- the house

class House:
    def __init__(self):
        self.busy = False
        self.lock = threading.Lock()
        self.pending_task = None      # set when Winston asked Big Brother a question about a task
        self.last_files = ""
        self.chat = []                # recent conversation between Big Brother and Winston
        self.head_timer = None        # Winston leaves the chair after a while with no messages

    def start_task(self, text, file_ids=()):
        with self.lock:
            if self.busy:
                return False
            self.busy = True
        if self.head_timer:
            self.head_timer.cancel()
        BUS.publish({"type": "busy", "busy": True})
        threading.Thread(target=self._run_safe, args=(text, list(file_ids)), daemon=True).start()
        return True

    def _run_safe(self, text, file_ids):
        try:
            self._run(text, file_ids)
        except urllib.error.URLError:
            diary("system", "I can't reach Ollama. Make sure the Ollama app is running "
                            "(look for the llama icon by the clock), then try again.", "error")
        except Exception as e:  # keep the house alive whatever happens
            diary("system", f"Something went wrong at Big Brother Inc.: {e}", "error")
        finally:
            self._finish()

    def _finish(self):
        for hid in HOUSEMATES:
            if hid != HEAD_ID:
                move(hid, "free")          # staff go back to their own routines
        move(HEAD_ID, "ceo")               # Winston waits in your office for a while
        self.head_timer = threading.Timer(120, lambda: move(HEAD_ID, "free"))
        self.head_timer.daemon = True
        self.head_timer.start()
        status("All quiet. Winston is waiting in your office.", working=None)
        with self.lock:
            self.busy = False
        BUS.publish({"type": "busy", "busy": False})

    def remember(self, who, text):
        self.chat.append((who, text[:1500]))
        self.chat = self.chat[-12:]

    def max_says(self, text, kind="message"):
        say(HEAD_ID, first_line(text))
        diary(HEAD_ID, text, kind)
        self.remember("Winston", text)

    # -- the main loop: your office -> department -> Thought Police -> Winston brings it back
    def _run(self, text, file_ids):
        head = HOUSEMATES[HEAD_ID]
        names = [FILES[f]["name"] for f in file_ids if f in FILES]
        diary("user", text + ("\n\nAttached: " + ", ".join(names) if names else ""))

        files_text = files_block(file_ids)
        if files_text:
            self.last_files = files_text
        elif self.pending_task is not None:
            files_text = self.last_files

        clarified = self.pending_task is not None
        task = f"{self.pending_task}\n\nBig Brother's answer to your question: {text}" if clarified else text
        self.pending_task = None
        history = self.history_text()
        self.remember("Big Brother", text + (f" [attached: {', '.join(names)}]" if names else ""))

        # 1. Winston comes to Big Brother's office and listens
        move(HEAD_ID, "ceo")
        status(f"{head['name']} is in your office, listening", working=HEAD_ID)
        time.sleep(2)
        plan = self.plan(task + summarise_files(file_ids), history, allow_question=not clarified)
        mode = str(plan.get("mode", "task")).lower()
        reply = str(plan.get("reply") or "").strip()

        if mode == "chat":
            self.max_says(reply or "I'm here, Big Brother. What do you need?")
            return
        if mode == "question" and not clarified:
            self.pending_task = task
            self.max_says(reply or "Could you tell me a bit more about what you need?", "question")
            return

        assignments = self.clean_assignments(plan.get("assignments"))
        crew = ", ".join(HOUSEMATES[a["housemate"]]["name"] for a in assignments)
        self.max_says((reply or "Leave it with me, I'll get the right people on it.") + f"\n\nAssigned: {crew}")

        # 2. Winston heads to the office floor and briefs the department(s)
        for a in assignments:
            move(a["housemate"], "floor")
        move(HEAD_ID, "floor:" + assignments[0]["housemate"])
        time.sleep(3)

        # 3. Each staff member does their part at their desk, building on earlier work
        contributions = []
        for a in assignments:
            hid = a["housemate"]
            h = HOUSEMATES[hid]
            move(HEAD_ID, "floor:" + hid)
            if contributions:
                prev = HOUSEMATES[contributions[-1]["housemate"]]["name"]
                say(hid, f"Thanks {prev}, I'll take it from here.")
            else:
                say(hid, random.choice(["On it!", "Leave it with me.", "Right, let's do this."]))
            status(f"{h['name']} the {h['role']} is working ({MODEL_FOR[hid]})", working=hid)
            output = self.work(hid, task + files_text, a["subtask"], contributions)
            contributions.append({"housemate": hid, "subtask": a["subtask"], "output": output})
            say(hid, "Done: " + first_line(output))

        # 4. Combine the work into one answer
        if len(contributions) == 1:
            draft = contributions[0]["output"]
        else:
            status(f"{head['name']} is pulling everyone's work together", working=HEAD_ID)
            say(HEAD_ID, "Let me pull all of this together.")
            draft = self.compose(task, contributions)

        lead = contributions[-1]["housemate"]
        workers = [c["housemate"] for c in contributions]
        review = plan.get("review", True)
        review = not (review is False or str(review).lower() in ("false", "no", "0"))
        self.deliver(task, draft, lead, workers, review=review)

    def deliver(self, task, draft, lead, workers, max_rounds=None, review=True, reworked=False):
        """The Thought Police interrogate the work, then Winston takes it to Big Brother."""
        head = HOUSEMATES[HEAD_ID]
        if max_rounds is None:
            max_rounds = SETTINGS.get("max_revisions", 1)
        verdict = None
        for round_no in range(1, max_rounds + 2):
            if not review:
                break
            for v in BOARD:
                move(v, "board")
            move(lead, "board")
            move(HEAD_ID, "board")
            say(lead, "Here's our work for the Thought Police...")
            status("The Thought Police are interrogating the work", working=None)
            time.sleep(4)
            verdict = self.council(task, draft, BOARD, round_no)
            if verdict["approved"] or round_no > max_rounds:
                break
            fixes = "\n".join(f"- {HOUSEMATES[v['id']]['name']}: {v['fix'] or v['reason']}" for v in verdict["votes"])
            save_record(REJECTED_DIR, task, f"# {task[:200]}\n\n**Rejected by the Thought Police** "
                        f"(average {verdict['average']:.1f}/10, round {round_no}). Author: {HOUSEMATES[lead]['name']}\n\n"
                        + "\n".join(f"- **{HOUSEMATES[v['id']]['name']}** {v['score']}/10: {v['reason']} {v['fix']}" for v in verdict["votes"])
                        + f"\n\n---\n\n{draft}\n")
            say(lead, "Not Room 101...")
            status(f"{HOUSEMATES[lead]['name']} has been taken to Room 101 to fix what the Thought Police found", working=lead)
            move(lead, "room101")
            draft = self.revise(lead, task, draft, fixes)

        # Only Winston goes back to Big Brother's office to present it
        say(lead, "Over to you, Winston.")
        move(HEAD_ID, "ceo")
        status(f"{head['name']} is bringing the result to your office", working=None)
        time.sleep(4)
        helpers = [HOUSEMATES[w]["name"] for w in workers if w != lead]
        by_line = f"{HOUSEMATES[lead]['name']} did the final piece{' with help from ' + ', '.join(helpers) if helpers else ''}"
        if reworked:
            intro = (f"Here it is again, Big Brother. {HOUSEMATES[lead]['name']} reworked it in Room 101 from your notes. "
                     f"Approve it, or send it back again.")
        elif verdict is None:
            intro = (f"Here's the finished work, Big Brother. {by_line}. It was a quick job, so I brought it "
                     f"straight to you without troubling the Thought Police. Approve it, or send it back with your notes.")
        else:
            intro = (f"Here's the finished work, Big Brother. {by_line}, and the Thought Police "
                     f"{'cleared it' if verdict['approved'] else 'still had doubts, so check it carefully'} "
                     f"({verdict['average']:.1f}/10). Approve it for release, or send it back with your notes.")
        say(HEAD_ID, "Here's the finished work, Big Brother.")
        diary(HEAD_ID, draft, "result")
        diary(HEAD_ID, intro, "verdict")
        self.remember("Winston", f"(Delivered the result for: {task[:200]}) {draft[:800]}")
        self.last_result = {"task": task, "draft": draft, "lead": lead, "workers": workers}

    # -- Big Brother's decision on the last result
    def decide(self, decision, notes):
        result = getattr(self, "last_result", None)
        if not result:
            return False, "There's nothing waiting for your decision."
        if decision == "approve":
            name = save_record(RELEASED_DIR, result["task"], f"# {result['task'][:200]}\n\n{result['draft']}\n")
            self.last_result = None
            self.remember("Big Brother", "(Approved the work for release.)")
            say(HEAD_ID, "Released. Good work, everyone.")
            diary("system", f"Approved and released. Saved as released/{name}", "released")
            return True, name
        with self.lock:
            if self.busy:
                return False, "The office is busy. Try again in a moment."
            self.busy = True
        if self.head_timer:
            self.head_timer.cancel()
        self.last_result = None
        BUS.publish({"type": "busy", "busy": True})
        threading.Thread(target=self._send_back_safe, args=(result, notes), daemon=True).start()
        return True, ""

    def _send_back_safe(self, result, notes):
        try:
            lead = result["lead"]
            diary("user", "Sent back: " + (notes or "Not good enough. Improve it."))
            save_record(REJECTED_DIR, result["task"], f"# {result['task'][:200]}\n\n**Rejected by Big Brother.** "
                        f"Author: {HOUSEMATES[lead]['name']}\n\n- Notes: {notes or 'Not good enough.'}\n\n---\n\n{result['draft']}\n")
            self.remember("Big Brother", f"(Sent the work back) {notes}")
            say(HEAD_ID, "Understood. Room 101 it is.")
            move(lead, "room101")
            move(HEAD_ID, "room101")
            time.sleep(4)
            move(HEAD_ID, "ceo")
            status(f"{HOUSEMATES[lead]['name']} is reworking it in Room 101 from your notes", working=lead)
            draft = self.revise(lead, result["task"], result["draft"],
                                f"- Big Brother himself: {notes or 'Not good enough. Make it clearly better.'}")
            self.deliver(result["task"], draft, lead, result["workers"], max_rounds=0, review=False, reworked=True)
        except urllib.error.URLError:
            diary("system", "I can't reach Ollama. Make sure the Ollama app is running, then try again.", "error")
        except Exception as e:
            diary("system", f"Something went wrong at Big Brother Inc.: {e}", "error")
        finally:
            self._finish()

    def history_text(self):
        if not self.chat:
            return "(This is the start of the conversation.)"
        return "\n".join(f"{who}: {text}" for who, text in self.chat)

    # ------------------------------------------------------------ steps

    def plan(self, message, history, allow_question):
        head = HOUSEMATES[HEAD_ID]
        q_line = ('"question": the request is a job but genuinely too vague to start; "reply" is ONE short '
                  'clarifying question.\n') if allow_question else ""
        system = (
            f"{persona(head)}\n"
            "You are the only staff member who talks to Big Brother, in Big Brother's office. You are their friendly, "
            "capable right hand. You can chat, but you NEVER do real work yourself (writing, coding, research, "
            "planning, marking): you hand that to the right staff, the Thought Police reviews it, and you "
            "bring back the result.\n\n"
            f"Staff you can assign:\n{roster()}\n\n"
            "Decide the mode:\n"
            '"chat": greetings, small talk, questions about the company, the staff or earlier results. '
            '"reply" is your natural spoken answer (1-4 sentences).\n'
            f"{q_line}"
            '"task": anything that needs real work. "reply" is one or two sentences telling Big Brother who you are '
            'putting on it. Fill "assignments" with 1 to 3 staff, in order, each with a clear specific sub-task.\n'
            "For university or college work: the Professor goes first to break down the brief and marking criteria, "
            "then the Scholar produces the work following the Professor's plan. If Big Brother only wants feedback "
            "or marking on their own work, use just the Professor.\n"
            "For an image, logo, icon, poster or drawing: give it to the Creative Lead and ask for the picture as SVG "
            "code in a ```svg code block (it is shown to Big Brother as a real image).\n\n"
            f"Conversation so far:\n{history}\n\n"
            'For a task, also decide "review": true if the work is substantial or matters (essays, assignments, '
            'code, plans, anything that could go wrong), so the Thought Police inspect it first; false for quick, '
            'simple things (a short answer, a few names or ideas, a quick message) so it comes straight back.\n'
            'Reply ONLY with JSON: {"mode": "chat" | "question" | "task", "reply": "...", "review": true | false, '
            '"assignments": [{"housemate": "<id>", "subtask": "<instruction>"}]}'
        )
        return parse_json(ollama_chat(HEAD_ID, system, f"Big Brother says: {message}", json_mode=True))

    def clean_assignments(self, raw):
        clean = []
        for a in raw or []:
            if not isinstance(a, dict):
                continue
            hid = str(a.get("housemate", "")).strip().lower()
            if hid in STAFF and hid not in [c["housemate"] for c in clean]:
                clean.append({"housemate": hid, "subtask": str(a.get("subtask") or "Do the task.")})
        if not clean:  # the Head fumbled: give it to the most general housemate
            fallback = "tutor" if "tutor" in STAFF else STAFF[0]
            clean = [{"housemate": fallback, "subtask": "Complete Big Brother's task fully."}]
        return clean[:3]

    def work(self, hid, task, subtask, contributions):
        h = HOUSEMATES[hid]
        earlier = ""
        if contributions:
            parts = [f"--- From {HOUSEMATES[c['housemate']]['name']} ({HOUSEMATES[c['housemate']]['role']}):\n"
                     f"{c['output'][:3000]}" for c in contributions]
            earlier = "\n\nYour colleagues' work so far (build on it, don't repeat it):\n" + "\n".join(parts)
        system = (
            f"{persona(h)}\nYour skills: {h.get('skills', '')}\n"
            f"Big Brother set this task: \"{task}\"\n"
            f"Winston, the Chief of Staff, gave you this part: \"{subtask}\"{earlier}\n\n"
            "Do your part fully and well. Write the actual output (the code, plan, breakdown or ideas), "
            "not a description of what you would do. Use Markdown. Don't mention the company or your "
            "colleagues in your output."
        )
        return ollama_chat(hid, system, subtask, live=True)

    def compose(self, task, contributions):
        head = HOUSEMATES[HEAD_ID]
        parts = "\n\n".join(f"--- {HOUSEMATES[c['housemate']]['name']} ({HOUSEMATES[c['housemate']]['role']}), "
                            f"who was asked to: {c['subtask']}\n{c['output']}" for c in contributions)
        system = (
            f"{persona(head)}\nCombine your staff's contributions into ONE final answer to Big Brother's "
            f"task: \"{task}\".\nKeep all the real substance (code, steps, plans, numbers) intact, remove "
            "repetition, and organise it clearly in Markdown. Don't add commentary about the company."
        )
        return ollama_chat(HEAD_ID, system, parts)

    def council(self, task, draft, voters, round_no):
        votes = []
        for v in voters:
            h = HOUSEMATES[v]
            status(f"Interrogation {round_no}: {h['name']}, {h['role']}, is reviewing", working=v)
            system = (
                f"{persona(h)}\nYou are a Thought Police agent: you only interrogate work, never make it. Judge "
                f"this anonymous piece of work, produced for Big Brother's request: \"{task[:3000]}\".\n"
                f"Your focus as {h['role']}: {h.get('focus', '')}\n"
                "Be strict but fair: does it fully and correctly do what was asked?\n"
                'Reply ONLY with JSON: {"score": <whole number 1-10>, "verdict": "approve" or "revise", '
                '"reason": "one sentence", "fix": "the single most important improvement, or an empty string"}'
            )
            result = parse_json(ollama_chat(v, system, draft[:12000], json_mode=True))
            try:
                score = max(1, min(10, int(float(result.get("score", 5)))))
            except Exception:
                score = 5
            vote = {
                "id": v,
                "score": score,
                "verdict": "approve" if str(result.get("verdict", "")).lower().startswith("approve") else "revise",
                "reason": str(result.get("reason", "")),
                "fix": str(result.get("fix", "")),
            }
            votes.append(vote)
            say(v, f"{score}/10. {vote['reason']}")
            BUS.publish({"type": "vote", "round": round_no, **vote})
        average = sum(x["score"] for x in votes) / max(1, len(votes))
        approvals = sum(1 for x in votes if x["verdict"] == "approve")
        approved = average >= SETTINGS.get("council_pass_score", 6) and approvals * 2 >= len(votes)
        BUS.publish({"type": "council", "round": round_no, "average": average, "approved": approved})
        return {"approved": approved, "average": average, "votes": votes}

    def revise(self, hid, task, draft, fixes):
        h = HOUSEMATES[hid]
        system = (
            f"{persona(h)}\nThe Thought Police sent your work back. Big Brother's request was: \"{task}\".\n"
            f"Thought Police feedback:\n{fixes}\n\n"
            "Rewrite the COMPLETE answer, fixing these issues. Output the full improved answer in Markdown, "
            "not just the changes, and don't mention the Thought Police."
        )
        return ollama_chat(hid, system, draft, live=True)


HOUSE = House()


# ---------------------------------------------------------------- talking to someone in person

DIRECT_CHATS = {}       # housemate id -> recent conversation with Big Brother
DIRECT_BUSY = set()


def direct_chat(hid, text, file_ids):
    h = HOUSEMATES[hid]
    names = [FILES[f]["name"] for f in file_ids if f in FILES]
    diary("user", text + ("\n\nAttached: " + ", ".join(names) if names else ""), "direct", to=hid)
    history = DIRECT_CHATS.setdefault(hid, [])
    past = "\n".join(f"{who}: {t}" for who, t in history[-10:]) or "(You haven't spoken before.)"
    if h.get("board"):
        job = f"You are a Thought Police agent. Your focus: {h.get('focus', '')}"
    elif hid == HEAD_ID:
        job = "You are Big Brother's Chief of Staff."
    else:
        job = f"Your skills: {h.get('skills', '')}"
    system = (
        f"{persona(h)}\n{job}\n"
        "Big Brother himself has just walked over and is standing beside you, speaking to you directly. "
        "Stay in character. Be helpful and honest. Keep chat short (1-5 sentences), but if Big Brother asks "
        "for real work in your area, do it properly and in full, using Markdown.\n\n"
        f"Your conversation with Big Brother so far:\n{past}"
    )
    try:
        status(f"{h['name']} is answering you", working=hid)
        reply = ollama_chat(hid, system, text + files_block(file_ids), live=True)
        diary(hid, reply, "direct")
        say(hid, first_line(reply))
        history.append(("Big Brother", text[:1500]))
        history.append((h["name"], reply[:1500]))
        DIRECT_CHATS[hid] = history[-20:]
    except urllib.error.URLError:
        diary("system", "I can't reach Ollama. Make sure the Ollama app is running, then try again.", "error")
    except Exception as e:
        diary("system", f"{h['name']} couldn't answer: {e}", "error")
    finally:
        DIRECT_BUSY.discard(hid)
        status("Big Brother is out on the floor.", working=None)
        BUS.publish({"type": "direct-done", "id": hid})


# ---------------------------------------------------------------- web server

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"
        if path == "/events":
            return self._events()
        if path == "/api/records":
            return self._send(200, json.dumps(list_records()))
        if path.startswith("/api/record/"):
            parts = path.split("/")
            if len(parts) == 5 and parts[3] in ("approved", "rejected"):
                folder = RELEASED_DIR if parts[3] == "approved" else REJECTED_DIR
                name = os.path.basename(urllib.parse.unquote(parts[4]))
                full = os.path.join(folder, name)
                if name.endswith(".md") and os.path.isfile(full):
                    with open(full, "r", encoding="utf-8") as f:
                        return self._send(200, json.dumps({"text": f.read()}))
            return self._send(404, '{"error": "No such record"}')
        if path == "/api/state":
            warnings = refresh_models()
            mates = [{"id": hid, "name": h["name"], "role": h["role"], "color": h["color"], "department": h.get("department", ""), "board": bool(h.get("board")),
                      "model": MODEL_FOR.get(hid, h.get("model")), "room": BUS.positions.get(hid)}
                     for hid, h in HOUSEMATES.items()]
            return self._send(200, json.dumps({
                "version": 7, "unpersons": UNPERSONS, "housemates": mates, "busy": HOUSE.busy, "warnings": warnings,
                "ollama": bool(INSTALLED_MODELS), "history": BUS.diary_history,
                "awaitingAnswer": HOUSE.pending_task is not None,
                "awaitingDecision": getattr(HOUSE, "last_result", None) is not None,
            }))
        file_path = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if file_path.startswith(STATIC_DIR) and os.path.isfile(file_path):
            ctype = {"html": "text/html", "js": "application/javascript",
                     "css": "text/css"}.get(file_path.rsplit(".", 1)[-1], "application/octet-stream")
            with open(file_path, "rb") as f:
                return self._send(200, f.read(), ctype + "; charset=utf-8")
        self._send(404, '{"error": "not found"}')

    def do_POST(self):
        if self.path == "/api/task":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                text = str(body.get("text", "")).strip()
                file_ids = [f for f in body.get("files", []) if f in FILES]
            except Exception:
                text, file_ids = "", []
            if not text and file_ids:
                text = "Please look at the attached file(s)."
            if not text:
                return self._send(400, '{"error": "Empty task"}')
            if not HOUSE.start_task(text, file_ids):
                return self._send(409, '{"error": "The office is busy with a job. Give it a moment."}')
            return self._send(200, '{"ok": true}')
        if self.path == "/api/direct":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                body = {}
            hid = str(body.get("to", ""))
            text = str(body.get("text", "")).strip()
            file_ids = [f for f in body.get("files", []) if f in FILES]
            if hid not in HOUSEMATES or (not text and not file_ids):
                return self._send(400, '{"error": "Nobody to talk to, or nothing to say."}')
            if hid in DIRECT_BUSY:
                return self._send(409, '{"error": "They are still answering you."}')
            DIRECT_BUSY.add(hid)
            threading.Thread(target=direct_chat, args=(hid, text or "Please look at the attached file(s).", file_ids),
                             daemon=True).start()
            return self._send(200, '{"ok": true}')
        if self.path == "/api/decision":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                body = {}
            ok, info = HOUSE.decide(str(body.get("decision", "")), str(body.get("notes", "")).strip())
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "info": info, "error": "" if ok else info}))
        if self.path == "/api/upload":
            length = int(self.headers.get("Content-Length", 0))
            if length > 40 * 1024 * 1024:
                return self._send(413, '{"error": "That file is too big (40 MB max)."}')
            try:
                body = json.loads(self.rfile.read(length))
                name = os.path.basename(str(body["name"]))
                raw = base64.b64decode(body["data"])
                text = extract_text(name, raw)
            except Exception as e:
                return self._send(400, json.dumps({"error": f"Couldn't read that file: {e}"}))
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
                f.write(raw)
            fid = f"f{int(time.time() * 1000)}{random.randint(100, 999)}"
            FILES[fid] = {"name": name, "text": text}
            return self._send(200, json.dumps({"id": fid, "name": name, "chars": len(text)}))
        self._send(404, '{"error": "not found"}')

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        q = BUS.subscribe()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            BUS.unsubscribe(q)


def main():
    port = SETTINGS.get("port", 8765)
    warnings = refresh_models()
    print("=" * 56)
    print("  BIG BROTHER INC.")
    print("=" * 56)
    if not INSTALLED_MODELS:
        print("  WARNING: can't reach Ollama. Open the Ollama app first.")
    for w in warnings:
        print("  NOTE: " + w)
    for hid, h in HOUSEMATES.items():
        print(f"  {h['name']:<6} {h['role']:<17} -> {MODEL_FOR.get(hid)}")
    server = None
    for _ in range(6):                     # an old copy may still be closing down
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            time.sleep(1)
    if server is None:
        print(f"\n  Port {port} is in use. Is Big Brother already running? "
              f"Open http://localhost:{port} in your browser.")
        input("\n  Press Enter to close.")
        return
    url = f"http://localhost:{port}"
    print(f"\n  Big Brother Inc. is open at {url}")
    print("  Keep this window open while you use it. Close it to shut Big Brother down.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
