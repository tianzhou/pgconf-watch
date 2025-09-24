#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Set
import requests
from bs4 import BeautifulSoup


def fetch_conferences() -> List[Dict]:
    """Fetch and parse conference data from PostgreSQL website."""
    url = "https://www.postgresql.org/about/newsarchive/conferences/"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.content, 'html.parser')
    conferences = []

    # Find all conference entries - they're typically in divs or sections
    content_area = soup.find('div', {'id': 'pgContentWrap'}) or soup.find('main') or soup

    # Look for conference information patterns
    text_content = content_area.get_text()
    lines = [line.strip() for line in text_content.split('\n') if line.strip()]

    current_conference = {}
    in_conference_section = False

    for i, line in enumerate(lines):
        # Skip navigation and header content
        if any(skip in line.lower() for skip in ['navigation', 'search', 'menu', 'header']):
            continue

        # Look for conference patterns
        if any(conf_word in line.lower() for conf_word in ['pgconf', 'pgday', 'postgresql conference', 'nordic pgday']):
            if current_conference:
                conferences.append(current_conference)

            current_conference = {
                'name': line.strip(),
                'details': [],
                'parsed_date': None,
                'location': None,
                'status': None
            }
            in_conference_section = True
        elif in_conference_section and line:
            # Collect details for current conference
            current_conference['details'].append(line)

            # Parse specific information
            if re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)', line, re.I):
                current_conference['parsed_date'] = line

            if any(location_word in line.lower() for location_word in ['location:', 'hotel', 'city', 'country']):
                current_conference['location'] = line

            if any(status_word in line.lower() for status_word in ['call for papers', 'registration', 'schedule', 'published']):
                current_conference['status'] = line

        # End conference section on empty line or new major section
        elif in_conference_section and not line:
            if current_conference:
                conferences.append(current_conference)
                current_conference = {}
            in_conference_section = False

    # Add last conference if exists
    if current_conference:
        conferences.append(current_conference)

    # Clean and deduplicate conferences
    cleaned_conferences = []
    seen_names = set()

    for conf in conferences:
        if conf['name'] and conf['name'] not in seen_names:
            # Create a unique identifier
            conf['id'] = re.sub(r'[^\w\s-]', '', conf['name']).strip().replace(' ', '_').lower()
            cleaned_conferences.append(conf)
            seen_names.add(conf['name'])

    return cleaned_conferences


def load_previous_data(data_file: str) -> List[Dict]:
    """Load previously stored conference data."""
    if not os.path.exists(data_file):
        return []

    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading previous data: {e}")
        return []


def save_current_data(data_file: str, conferences: List[Dict]) -> None:
    """Save current conference data."""
    try:
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(conferences, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving data: {e}")
        sys.exit(1)


def compare_conferences(old_data: List[Dict], new_data: List[Dict]) -> Dict:
    """Compare old and new conference data and return changes."""
    old_conferences = {conf['id']: conf for conf in old_data}
    new_conferences = {conf['id']: conf for conf in new_data}

    old_ids = set(old_conferences.keys())
    new_ids = set(new_conferences.keys())

    changes = {
        'added': [],
        'removed': [],
        'modified': []
    }

    # Find added conferences
    for conf_id in new_ids - old_ids:
        changes['added'].append(new_conferences[conf_id])

    # Find removed conferences
    for conf_id in old_ids - new_ids:
        changes['removed'].append(old_conferences[conf_id])

    # Find modified conferences
    for conf_id in old_ids & new_ids:
        old_conf = old_conferences[conf_id]
        new_conf = new_conferences[conf_id]

        # Compare key fields
        if (old_conf.get('details') != new_conf.get('details') or
            old_conf.get('parsed_date') != new_conf.get('parsed_date') or
            old_conf.get('location') != new_conf.get('location') or
            old_conf.get('status') != new_conf.get('status')):
            changes['modified'].append({
                'id': conf_id,
                'old': old_conf,
                'new': new_conf
            })

    return changes


def create_issue_body(changes: Dict, all_conferences: List[Dict]) -> str:
    """Create GitHub issue body from changes."""
    body = f"# PostgreSQL Conference Changes Detected\n\n"
    body += f"**Detection Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"

    if changes['added']:
        body += "## 🆕 New Conferences Added\n\n"
        for conf in changes['added']:
            body += f"### {conf['name']}\n"
            for detail in conf['details'][:5]:  # Limit details
                body += f"- {detail}\n"
            body += "\n"

    if changes['removed']:
        body += "## ❌ Conferences Removed\n\n"
        for conf in changes['removed']:
            body += f"- **{conf['name']}**\n"
        body += "\n"

    if changes['modified']:
        body += "## 📝 Conference Updates\n\n"
        for change in changes['modified']:
            body += f"### {change['new']['name']}\n"
            body += "**Changes detected in conference details**\n\n"

    # Add section showing all current conferences
    body += "## 📋 All Current Conferences\n\n"
    body += f"*Total conferences tracked: {len(all_conferences)}*\n\n"

    # Group conferences by type/status for better organization
    active_conferences = []
    call_for_papers = []
    schedule_published = []
    other_conferences = []

    for conf in all_conferences:
        name_lower = conf['name'].lower()
        details_str = ' '.join(conf.get('details', [])).lower()

        if 'call for papers' in name_lower or 'call for papers' in details_str:
            call_for_papers.append(conf)
        elif 'schedule' in name_lower and ('published' in name_lower or 'online' in name_lower):
            schedule_published.append(conf)
        elif any(event in name_lower for event in ['pgconf', 'pgday', 'postgresql conference']):
            active_conferences.append(conf)
        else:
            other_conferences.append(conf)

    if call_for_papers:
        body += "### 📢 Call for Papers Open\n"
        for conf in call_for_papers[:10]:  # Limit to avoid too long issues
            body += f"- **{conf['name']}**\n"
        if len(call_for_papers) > 10:
            body += f"- *... and {len(call_for_papers) - 10} more*\n"
        body += "\n"

    if schedule_published:
        body += "### 📅 Schedule Published\n"
        for conf in schedule_published[:10]:
            body += f"- **{conf['name']}**\n"
        if len(schedule_published) > 10:
            body += f"- *... and {len(schedule_published) - 10} more*\n"
        body += "\n"

    if active_conferences:
        body += "### 🎯 Active Conferences\n"
        for conf in active_conferences[:15]:
            body += f"- **{conf['name']}**\n"
        if len(active_conferences) > 15:
            body += f"- *... and {len(active_conferences) - 15} more*\n"
        body += "\n"

    body += f"\n---\n*This issue was automatically created by the conference monitoring system.*"
    body += f"\n*Check the [source page](https://www.postgresql.org/about/newsarchive/conferences/) for full details.*"

    return body


def create_github_issue(title: str, body: str) -> None:
    """Create a GitHub issue using environment variables."""
    github_token = os.getenv('GITHUB_TOKEN')
    github_repository = os.getenv('GITHUB_REPOSITORY')

    if not github_token or not github_repository:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY environment variables are required")
        return

    url = f"https://api.github.com/repos/{github_repository}/issues"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }

    data = {
        'title': title,
        'body': body,
        'labels': ['conference-update', 'automated']
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        issue_data = response.json()
        print(f"✅ Created issue #{issue_data['number']}: {title}")
        print(f"🔗 {issue_data['html_url']}")
    except requests.RequestException as e:
        print(f"❌ Error creating GitHub issue: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")


def main():
    """Main function to check conferences and create issues if needed."""
    data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'conferences.json')

    print("🔍 Fetching current conference data...")
    current_conferences = fetch_conferences()
    print(f"📊 Found {len(current_conferences)} conferences")

    print("📂 Loading previous conference data...")
    previous_conferences = load_previous_data(data_file)
    print(f"📊 Previous data contained {len(previous_conferences)} conferences")

    print("🔄 Comparing conference data...")
    changes = compare_conferences(previous_conferences, current_conferences)

    total_changes = len(changes['added']) + len(changes['removed']) + len(changes['modified'])

    if total_changes > 0:
        print(f"🚨 Changes detected:")
        print(f"  - Added: {len(changes['added'])}")
        print(f"  - Removed: {len(changes['removed'])}")
        print(f"  - Modified: {len(changes['modified'])}")

        # Create GitHub issue
        title = f"PostgreSQL Conference Changes - {datetime.now().strftime('%Y-%m-%d')}"
        issue_body = create_issue_body(changes, current_conferences)

        if os.getenv('GITHUB_TOKEN'):
            create_github_issue(title, issue_body)
        else:
            print("⚠️  No GITHUB_TOKEN found, issue creation skipped")
            print(f"\nIssue would be:\n{title}\n{issue_body}")
    else:
        print("✅ No changes detected")

    print("💾 Saving current conference data...")
    save_current_data(data_file, current_conferences)

    print("🎉 Conference monitoring complete!")


if __name__ == "__main__":
    main()