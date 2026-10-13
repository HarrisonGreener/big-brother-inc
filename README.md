# Big Brother Inc.

*A pixel-art experiment in multi-agent AI, inspired by George Orwell's* Nineteen Eighty-Four.

You play Big Brother. Beneath you is a small company of AI "staff", each one a language model running locally on
your own computer through [Ollama](https://ollama.com). You give an order; you watch the building carry it out.
Every message is relayed, every draft is inspected, and nothing reaches you without passing the Thought Police.

**[Explore the live demo](https://harrygreener01-cloud.github.io/big-brother-inc/)**

![The Big Brother Inc. building](docs/building.png)

> **Please read before downloading.** Big Brother Inc. is a creative and technical project, not a dependable AI
> product. It runs small open-source models on ordinary home hardware, so it's slow, its answers can be wrong
> or odd, and parts of it are deliberately theatrical. It was built to explore how several AI agents can be
> organised to work together, and to have some fun with Orwell along the way. Treat anything it produces as a
> curiosity, not advice.

## The idea

Most AI assistants are a single voice in a chat box. Orwell's Oceania is the opposite: a vast bureaucracy where
every task passes through ministries, records are rewritten, and everything is watched and judged. That made it
a natural setting for a question I wanted to explore: **what happens if, instead of asking one model, you build
an organisation of them?** One model routes the work, others specialise, and a separate group does nothing but
criticise.

The 1984 setting isn't just decoration. Most of the book's ideas map onto a real part of the system.

## How Orwell shaped the features

| In the book | In Big Brother Inc. | Why it's there |
|---|---|---|
| **Big Brother**, the face no one meets | You. You never do the work; you give orders and pass judgement. | The human stays in charge: nothing is "released" until you approve it. |
| **Winston Smith**, the clerk who handles records | Winston, your Chief of Staff, the only one who reports to you | A *router* agent. He decides whether a message is chat, needs a question, or should go to a department, and whether it deserves review. |
| **The Ministries** and their departments | Engineering, Academic, Business and Creative rooms | *Specialist* agents, each with its own persona, skills and model. Later staff build on earlier staff's work. |
| **The Thought Police** | O'Brien, Charrington and Martin, who only ever judge | *Reviewer* agents. They score every substantial piece of work blind and hold up scorecards. Each runs on a different model family, so they make different mistakes and catch different errors. |
| **Room 101** | Where guilty work, and its author, are sent | A *revision loop*. Work that fails review is rewritten using the reviewers' notes, then judged again. |
| **The memory hole** | Rejected drafts are dropped down a slot in the wall | A visual record that failure happened. Every rejected draft is also kept in the Records archive. |
| **Telescreens** | Screens in every room, live CCTV in Surveillance, and a scrolling announcement ticker | *Observability.* You can watch each agent think: their screen fills as they write, and every step appears in the building feed. |
| **Unpersons** | Remove a staff member and they "never existed" | Staff are just entries in a config file, and the building keeps a record of who was erased. |
| **The Two Minutes Hate** | Call a meeting and everyone files into the Assembly Room for a rally | Pure atmosphere, and a demonstration of coordinating every character at once. |

![Thought Police scorecards](docs/thought-police.png)

## Features

- **An office you can watch.** A top-down pixel-art building drawn on a canvas, with hand-made sprites, corridor
  pathfinding, a day/night cycle that follows the real clock, zoom and pan, and procedurally generated sound.
- **Delegation.** Winston reads each request and assigns one to three staff in order. Quick jobs come straight
  back; substantial ones are sent for review.
- **Blind review.** The Thought Police score anonymous work out of 10. Guilty work goes to Room 101 for one round
  of fixes before Winston brings it to you.
- **Your verdict.** Approve work for release, or send it back with notes. Approved and rejected work both stay in
  the **Records** archive.
- **Talk to anyone.** Walk over to any member of staff, or call them into your office, and speak to them directly.
- **Files in, real output out.** Staff can read PDFs, Word documents, slides, text and code. Images (drawn as SVG)
  and web pages appear as real pictures and live previews, not just code.
- **A living building.** Staff keep office hours, take canteen breaks and get spot checks from the Thought Police.
  Background clerks fill the departments.

![The Assembly Room](docs/assembly-room.png)

## How it's built

```
You (Big Brother)
   |
Winston (router)  -------  chat, ask a question, or delegate - and decide whether review is needed
   |
Departments (specialists)  each a local model with its own persona; writing streams live to the screen
   |
Thought Police (reviewers)  three blind judges on different models; failures go to Room 101
   |
Winston -> You  ----------  approve for release, or send back with notes
```

- **Backend:** one dependency-free Python file (`server.py`). It orchestrates the agents, calls Ollama's API,
  streams events to the browser with Server-Sent Events, and handles files and records.
- **Frontend:** one HTML file (`static/index.html`) for the whole building, interface and animation.
- **Cast:** every character's name, role, personality and model lives in `housemates.json`.
- **Demo mode** (`static/demo.js`): the version online runs without a server. Replies are scripted, with an
  option to load a small model that runs inside your browser (WebGPU, Chrome or Edge).

## Running it yourself

You'll need a reasonably modern graphics card (it was developed on a 12 GB RTX 3060) and some patience.

1. Install [Ollama](https://ollama.com) and [Python](https://www.python.org/downloads/).
2. Download at least the default model: `ollama pull gemma4:12b`. Optionally add `qwen2.5-coder:14b`,
   `qwen3.5:9b` and `granite4.2:8b` so the staff think in different ways.
3. Run `python server.py` (on Windows, double-click `start_house.bat`) and open http://localhost:8765.

Anyone whose model isn't installed borrows the default, so one model is enough to try it.

---

*Inspired by George Orwell's* Nineteen Eighty-Four *(1949). This is an independent fan project; all slogans,
characters' dialogue and artwork here are original.*
