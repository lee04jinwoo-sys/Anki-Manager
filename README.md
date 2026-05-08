# Anki Manager CLI 🚀

A powerful, modular CLI tool to automate your Anki workflow. Seamlessly fetch content, enrich notes with AI, manage card designs, and track your learning progress.

## ✨ Key Features

### 1. Add Notes (Smart Automation)
*   **YouTube**: Fetch transcripts and automatically select key sentences and vocabulary.
*   **Situation**: Generate contextual learning material based on a simple description.
*   **Obsidian**: Sync your "Inbox" notes directly into Anki.
*   **AI Enrichment**: Automatically fills definitions, examples, and translations.

### 2. Organize Notes (Maintenance)
*   **Audio Filler**: Automatically add high-quality TTS audio to your cards.
*   **Field Completion**: Auto-fill missing fields across all note models.
*   **Auto-Organizer**: Smart card migration and deck organization.
*   **Duplicate Cleaner**: Keep your collection lean by removing redundant cards.

### 3. Design Management
*   **Import/Export**: Manage your Anki card templates and CSS as JSON files.
*   **Version Control**: Keep your card designs safe and easily synchronizable across profiles.

### 4. Statistics & Analytics
*   **Performance Tracking**: Quick overview of deck retention and new card progress.
*   **Visual Reports**: Clean, table-based statistics directly in your terminal.

## ⌨️ Advanced Interactive Selector
The CLI features a modern, color-coded interactive selector:
*   **Visual Feedback**: [green]ON[/] / [red]OFF[/] backgrounds for selection.
*   **Bulk Actions**: `A` (Select All), `N` (Deselect None).
*   **Language Support**: Shortcuts work in both English and Korean (`ㅁ`, `ㅜ`, `ㅊ`, `ㅂ`).

## 🛠 Project Structure
```text
Anki Manager/
├── main.py           # Entry point
├── collectors/       # Data source handlers (YouTube, Obsidian)
├── core/             # Core logic (Generation, Selection, Completion)
├── integrations/     # External APIs (AnkiConnect, TTS)
├── utils/            # UI, Statistics, Design & Management tools
└── data/             # Configuration and logs
```

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   [Anki](https://apps.ankiweb.net/) with [AnkiConnect](https://ankiweb.net/shared/info/2055405234) installed.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/lee04jinwoo-sys/Anki-Manager.git
   cd "Anki Manager"
   ```
2. Set up virtual environment & Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure your `.env` file with necessary API keys.

### Usage
Run the interactive menu:
```bash
python main.py
```

## 📄 License
This project is for personal educational use.
