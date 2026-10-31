# SocioApp

SocioApp is a Flask-based social media dashboard that aggregates platform stats and account insights in one place.

## Overview

SocioApp helps creators and teams monitor cross-platform performance faster by combining social analytics into a single interface.

### Key Features

- Account linking and profile-based insights
- Unified dashboard view for multiple platforms
- Platform-specific stats pages (YouTube, Instagram, Twitter, Facebook, GitHub, Reddit)
- Flask backend with template-based frontend
- Modular utility files for social/API integrations

## Project Structure

- `socioapp/` - Main application code, static assets, and templates
- `.vscode/` - VS Code tasks/workspace config
- `.venv/` - Local virtual environment (excluded via `.gitignore`)

## Quick Start

1. Install dependencies:
   - `pip install -r socioapp/requirements.txt`
2. Run the app:
   - `python socioapp/app.py`
3. Open the local URL printed in your terminal.

## Notes

- Some integrations require API keys/OAuth credentials.
- This repo includes utility/demo files for multiple social platforms.

## License

No license specified yet.
