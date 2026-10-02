# Rasheed — Finance Savings Agent

A mobile app for expense tracking and savings, built around an AI agent
("Rasheed") with a friendly, encouraging personality. It's aimed at people
with irregular income — students, freelancers — who want to track spending
and hit savings goals without the usual friction of budgeting apps.

Built as a solo side project to learn how larger finance apps are built,
with an eventual goal of partnering with an e-wallet company.

## What it does

- **Three AI personas** (Wise / Disciplined / Energetic) — pick one during
  onboarding. Each has its own tone, a mood that reacts to your spending and
  goal progress, and (optionally) its own voice.
- **Quick expense logging** — tap a category icon, or just type a free-text
  note and the app guesses the category for you (Gemini-powered, with a
  rule-based fallback if no API key is configured).
- **Savings goals** with drag-to-reorder priority, and a gamified 10-stage
  path screen showing progress toward each one.
- **Fixed monthly expenses** (rent, subscriptions) — just a goal with a flag;
  it resets itself automatically at the start of each month.
- **Income allocation** — split one income transaction across several goals,
  always by your explicit choice (never auto-routed).
- **Chat with Rasheed** — a real multi-turn conversation. Rasheed can propose
  logging income, creating a goal, or correcting a category — but nothing
  changes your data until you tap confirm.
- **Receipt scanning (OCR)** — photograph a receipt; Gemini Vision reads the
  amount, suggests a category, and pre-fills the entry for you to review.
- **Bank SMS import** — paste a bank text message, or let the app scan your
  SMS inbox (Android, with your permission) and pick which messages to
  import. Built around Jordan's CliQ instant-payment format.
- **Text-to-speech** — Rasheed can read his replies aloud, with a distinct
  pitch/rate per persona.

Every AI-driven suggestion (category corrections, goal proposals, income
logging, etc.) is queued as a pending action and only applied after you
explicitly confirm it — nothing is changed automatically.

## Tech stack

| Layer | Technology |
|---|---|
| Mobile | Flutter (Riverpod for state management) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| AI | Google Gemini (`google-genai` SDK) — chat, vision (OCR), smart categorization |
| Auth | JWT |
| Containers | Docker Compose |

## Project status

The core app is fully built and tested: auth, categories, quick-log (manual
+ smart text categorization), goals (priority, recurring, deletion), personas
and onboarding, a mood-reactive chat agent with nudges, the confirm/reject
suggestion flow, OCR receipt scanning, SMS parsing and import, and
per-persona TTS.

**110 backend tests, all passing.**

**Not done yet:**
- General UI/UX polish (animations, demo seed data)
- Full API documentation pass
- Production hosting (currently runs locally via Docker)

## Running it locally

### Requirements
- Docker + Docker Compose
- Flutter SDK (for the mobile app)
- A [Gemini API key](https://aistudio.google.com/apikey) (optional — the app
  falls back to simple rule-based categorization without one, but chat, OCR,
  and TTS-adjacent AI features need it)

### Backend

```bash
# 1. Copy the env file and fill in your own values
cp .env.example .env
# at minimum, set JWT_SECRET_KEY and GEMINI_API_KEY

# 2. Build and start the backend + database
docker compose up -d --build

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Open the interactive API docs
# http://localhost:8000/docs
```

Required environment variables (see `app/config.py` for the full list and
defaults):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Secret used to sign auth tokens — **must** be changed from the default |
| `GEMINI_API_KEY` | Google Gemini API key — powers chat, OCR, and smart categorization |
| `AGENT_MODEL` | Gemini model name (Google renames these periodically — check [AI Studio](https://aistudio.google.com) if Rasheed stops responding) |

### Run the tests

```bash
docker compose exec backend pytest -v
```

### Mobile

```bash
cd mobile
flutter pub get
flutter run
```

By default the app points at `http://10.0.2.2:8000` (the Android emulator's
alias for your host machine). To run on a physical device or a device on a
different network, update `kApiBaseUrl` in `mobile/lib/core/api_client.dart`.

**Android permissions:** camera + photo access (receipt scanning) and SMS
read access (bank message import) need to be declared in
`android/app/src/main/AndroidManifest.xml` — see the comments in that file
for the exact entries.

## Project structure

```
backend/
├── app/
│   ├── main.py              # entry point — wires up the routers
│   ├── config.py            # settings, read from .env
│   ├── core/                 # auth, JWT, shared dependencies
│   ├── database/             # DB connection/session
│   ├── models/                # SQLAlchemy models (tables)
│   ├── schemas/               # Pydantic request/response shapes
│   ├── services/               # business logic
│   ├── api/routes/              # HTTP endpoints only — no business logic here
│   └── agent/                    # Rasheed: AI providers, mood engine, chat protocol
├── alembic/                       # migrations
└── tests/                          # pytest suite

mobile/
└── lib/
    ├── core/          # Riverpod providers, API client
    ├── models/        # data classes
    ├── services/      # API calls per domain (goals, transactions, agent...)
    ├── screens/       # one folder per screen
    ├── widgets/        # shared/reusable widgets
    └── theme/           # colors, personas' visual identity
```

## Architectural principles

1. **Service layer separate from the API layer** — `api/routes/` only
   handles HTTP in/out; all business logic lives in `services/`.
2. **Plugin-based data sources** — `Transaction.source` (manual / ocr / sms /
   open_banking) lets a new ingestion method be added without changing the
   core data model. OCR and SMS both plug into this today.
3. **UUIDs as primary keys**, not auto-increment — safer to expose, and
   scales better across services later.
4. **`Numeric`, not `Float`, for every money amount** — avoids rounding
   errors that `Float` would introduce.
5. **Every AI suggestion is a "pending action"** — nothing Rasheed proposes
   (a category fix, a new goal, logging income) touches your data until you
   explicitly confirm it. This is the core safety principle of the whole app.
6. **Review before save** — OCR and SMS parsing only ever return a draft;
   the existing quick-log save flow is still the one source of truth for
   actually writing a transaction.