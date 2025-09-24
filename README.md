# PostgreSQL Conference Monitor

Automated monitoring of PostgreSQL conferences from https://www.postgresql.org/about/newsarchive/conferences/

## How it works

- **Daily monitoring**: GitHub Actions runs every day at 9:00 AM UTC
- **Change detection**: Compares current conferences with previously saved data
- **Issue creation**: Creates GitHub issues when changes are detected
- **Notifications**: Users who watch this repository get notified of new issues

## Features

- Detects new conferences added
- Detects conferences removed
- Detects changes to existing conference details
- Stores conference data history
- Automated issue creation with detailed change information

## Files

- `.github/workflows/monitor-conferences.yml` - GitHub Actions workflow
- `scripts/check_conferences.py` - Main monitoring script
- `data/conferences.json` - Stored conference data for comparison
- `requirements.txt` - Python dependencies

## Manual Testing

To run the monitoring script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the monitoring script
python scripts/check_conferences.py
```

## GitHub Actions Configuration

The workflow automatically:
1. Fetches current conference data
2. Compares with stored data
3. Creates issues if changes detected
4. Updates stored data
5. Commits changes back to repository

No additional configuration required - just push to GitHub and the monitoring will start working.