# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Tutor Bot is a Telegram bot that delivers personalized quiz questions using OpenAI to help users learn any subject. Users set their subject of interest, receive daily questions, and get interactive tutoring help with hints and feedback.

## Commands

### Development
```bash
# Install dependencies (using uv)
uv sync

# Run linting
uv run ruff check
uv run ruff format

# Run the bot locally
uv run python main.py

# Run with Docker
docker-compose up --build
```

### Testing
Currently no automated tests are set up. Syntax validation can be done with:
```bash
uv run python -m py_compile main.py src/*.py
```

## Architecture

### Core Components

**main.py** - Bot entry point and command handlers
- Defines all Telegram bot commands and message handlers
- Manages bot lifecycle, scheduler, and status server
- Uses `main_bot_only()` for simple execution or `main()` for full setup with scheduler and status server

**src/openai_handler.py** - OpenAI integration layer
- Uses OpenAI **Chat Completions API** (migrated from Assistants API)
- Uses **GPT-5** model for all interactions
- Five different system prompts for different interaction types:
  - `GENERATION_SYSTEM_PROMPT` - Generates new questions (returns JSON)
  - `MESSAGE_SYSTEM_PROMPT` - Handles conversational messages and hints
  - `JUDGE_SYSTEM_PROMPT` - Evaluates solution attempts (returns JSON)
  - `GIVEUP_SYSTEM_PROMPT` - Provides full solutions when user gives up
  - `PLAY_SYSTEM_PROMPT` - Enables freeform chat mode
- Conversation history stored in database `messages` table instead of OpenAI threads
- Returns structured data using Pydantic models with JSON mode

**src/db.py** - Database layer
- Four models: `User`, `TutorSession`, `SolutionResponse`, `Message`
- PostgreSQL database via SQLAlchemy ORM
- `get_db_context()` provides database sessions throughout the app
- Session management: only one active (non-archived) session per user at a time
- `Message` model stores conversation history (role, content) for each session
- `get_session_messages()` retrieves conversation history for context

**src/scheduler.py** - Daily question scheduling
- `generate_daily_questions()` sends questions to all users with subjects
- Scheduled to run at 8am EST via APScheduler (configured in main.py)
- Admin can manually trigger via `/daily_question` command

### Key Data Flow

1. **Question Generation**: User requests question → `chat_generate_question()` calls GPT-5 with generation prompt → Returns `QuestionGeneration` model → Session stored in DB (no thread_id needed)

2. **Conversation**: User sends message → Retrieved session's conversation history from `messages` table → History + new message sent to GPT-5 → Response stored in `messages` table

3. **Solution Judging**: User submits via `/solve` → `chat_solution_attempt()` sends question + solution to GPT-5 with judge prompt → Returns `SolutionResponse` → Stored in DB → `chat_judge_response()` provides friendly summary

4. **Session Management**: New questions invalidate old sessions (set `archived=True`), ensuring only one active session per user

5. **Message Storage**: All user and assistant messages are stored in the `messages` table for conversation continuity and context

### Environment Variables

Required in `.env` (see `.env.example`):
- `TELEGRAM_BOT_TOKEN` - Bot token from BotFather
- `OPENAI_API_KEY` - OpenAI API key
- `DEVELOPER_CHAT_ID` - Telegram chat ID for error notifications
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` - PostgreSQL credentials
- `STATUS_SERVER_PORT` - Health check server port (default: 8080)

### Bot Commands

User commands:
- `/start` - Initialize user in database
- `/subject <text>` - Set/view learning subject
- `/memo <text>` - Set/view additional context notes
- `/question` - Request new question immediately
- `/hint` - Get hint on current question
- `/solve <answer>` - Submit solution for judging
- `/giveup` - Reveal solution and mark session complete
- `/freetalk` - Start freeform conversation mode

Admin commands:
- `/daily_question [user_ids...]` - Manually send daily questions

### Status Management

Users have a `status` field: "active" or "playing" (freetalk mode). When in "playing" mode, users are excluded from scheduled daily questions.
