import argparse
import concurrent.futures
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from translate_ifrs import decision_excerpt, fingerprint, localize
from ifric_papers import PaperIndex


ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://www.ifrs.org'
ARCHIVE = '/supporting-implementation/how-we-help-support-consistent-application/'
PLAN = '/projects/work-plan/'
UPDATES = '/news-and-events/updates/ifric/'
GROUPS = {'IFRIC': 'ifrs-interpretations-committee', 'IASB': 'international-accounting-standards-board'}
STANDARD = r'\b(?:IAS|IFRS|IFRIC|SIC)\s+\d+[A-Z]?\b'
MONTH = r'January|February|March|April|May|June|July|August|September|October|November|December'


def get(url):
    request = Request(urljoin(BASE, url), headers={'User-Agent': 'IFRS Research Tracker/1.0'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=22) as response:
                return response.read()
        except HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            if attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def page(url):
    return get(url).decode('utf-8-sig')


def plain(markup):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', markup)).split())


def official(path):
    url = urlsplit(urljoin(BASE, html.unescape(path)))
    if url.scheme != 'https' or url.hostname != 'www.ifrs.org':
        raise ValueError(f'Unexpected source host: {url.hostname}')
    path = url.path.removeprefix('/content/ifrs/home')
    if path.endswith('.html') and '/jcr:content/' not in path and not path.startswith('/content/'):
        path = path.removesuffix('.html') + '/'
    return BASE + path + ('#' + url.fragment if url.fragment else '')


def lazy_tab(markup, anchor):
    parent = re.search(r'IFRS\.tabs\("([^"]+)"\)', markup)
    name = re.search(r'<div name="([^"]+)"[^>]*data-anchor="' + anchor + r'"', markup)
    if not (parent and name):
        raise ValueError(f'Official tab not found: {anchor}')
    return page(f'{parent[1]}/{name[1]}.nocache.html')


def standards(*texts):
    return list(dict.fromkeys(m.upper() for text in texts for m in re.findall(STANDARD, text or '', re.I)))


def topic_key(title):
    title = re.split(r'[—–-]\s*(?:updated|Agenda Paper)\b', title, flags=re.I)[0]
    title = re.sub(r'^(?:IAS|IFRS|IFRIC|SIC)\s+\d+[^—–]+[—–]\s*', '', title, flags=re.I)
    title = re.sub(r'[\[(](?:(?:see\s+)?(?:IAS|IFRS|IFRIC|SIC)\s+\d+|Agenda Paper\b)[^)\]]*[)\]]', '', title, flags=re.I)
    return ' '.join(re.findall(r'[a-z0-9]+', title.lower()))


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def stable_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def archive_rows(markup):
    table = re.search(r'All agenda decisions\s*</span>.*?<tbody>(.*?)</tbody>', markup, re.S | re.I)
    if not table:
        raise ValueError('English agenda decision table is missing')
    result = {}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table[1], re.S):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)
        if len(cells) != 2:
            raise ValueError('Unexpected agenda decision row')
        document = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', cells[1], re.S)
        if not document or not plain(document[2]):
            raise ValueError('Agenda decision row lacks a document title or link')
        url = official(document[1])
        published = datetime.strptime(plain(cells[0]), '%d %b %Y').date().isoformat()
        result[url] = {'title': plain(document[2]), 'sourceUrl': url, 'publishedAt': published}
    if len(result) < 250:
        raise ValueError(f'Agenda decision table unexpectedly small: {len(result)}')
    return result


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def pdf_extractor():
    return shutil.which('pdftotext') or next(iter(ROOT.glob('tools/*/bin64/pdftotext.exe')), None)


def read_pdf(url, extractor, first_pages=None):
    if not extractor or not urlsplit(url).path.lower().endswith('.pdf'):
        return ''
    pdf = get(url)
    if not pdf.startswith(b'%PDF-'):
        raise ValueError('Source did not serve a PDF')
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / 'decision.pdf'
        source.write_bytes(pdf)
        page_args = ['-l', str(first_pages)] if first_pages else []
        result = subprocess.run([str(extractor), '-enc', 'UTF-8', '-nopgbrk', *page_args, str(source), '-'],
                                capture_output=True, check=True, timeout=25)
    text = result.stdout.decode('utf-8', errors='replace')
    return ' '.join(re.split(r'Copyright\s*©|©\s*IFRS Foundation', text, maxsplit=1, flags=re.I)[0].split())


def staff_context(url, extractor):
    try:
        text = read_pdf(url, extractor, first_pages=3)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Warning: staff paper context unavailable: {url}: {error}')
        return ''
    match = re.search(r'(?:The (?:Committee|IASB) received (?:a request|two submissions)|The request ask(?:ed|s)|This paper (?:asks|discusses|analyses))[^.]{25,440}\.', text, re.I)
    return match[0] if match else ''


def collect_decisions(rows, previous, today):
    old = {item['sourceUrl']: item for item in previous}
    extractor = pdf_extractor()

    def enrich(row):
        url = row['sourceUrl']
        existing = old.get(url, {})
        title, published = row['title'], row['publishedAt']
        text = existing.get('fullText', '')
        checked = existing.get('pdfCheckedAt', '')
        if not text or (published >= f'{today.year - 1}-01-01' and checked != today.isoformat()):
            try:
                extracted = read_pdf(url, extractor)
                if extracted:
                    text, checked = extracted, today.isoformat()
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f'Warning: could not index {url}: {error}')
        path_head = Path(urlsplit(url).path).name
        tags = standards(title, existing.get('standard'), re.sub('-', ' ', path_head), text[:260])
        if not tags:
            tags = standards(text)
        changed = bool(existing and (text != existing.get('fullText') or title != existing.get('title')))
        return {
            **existing, **row,
            'id': existing.get('id') or f'{published}-{slug(title)}-{stable_id(url)[:6]}',
            'standard': tags[0] if tags else '', 'standards': tags,
            'tags': ['agenda decision'], 'fullText': text,
            'volume': 'Official archive' if published >= '2019' else 'Historical archive',
            'pdfCheckedAt': checked,
            'lastChangedAt': today.isoformat() if changed else existing.get('lastChangedAt', published),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        current = list(pool.map(enrich, rows.values()))
    # The published catalogue can drop withdrawn documents. Keep previously indexed English entries.
    retained = [{**item, 'archiveOnly': True} for url, item in old.items()
                if url not in rows and 'standards' in item and not item['id'].startswith('historical-')]
    return sorted(current + retained, key=lambda row: (row['publishedAt'], row['title']), reverse=True)


def meeting_date(label):
    label = re.sub(r'\s+', ' ', label.strip())
    cross_month = re.match(rf'(\d{{1,2}} (?:{MONTH}))\s*[-–—].*?(\d{{4}})$', label)
    if cross_month:
        label = ' '.join(cross_month.groups())
    match = re.search(rf'(\d{{1,2}})(?:\s*[-–—]\s*\d{{1,2}})?\s+({MONTH})\s+(\d{{4}})$', label)
    if not match:
        raise ValueError(f'Unrecognized IFRS meeting date: {label}')
    return datetime.strptime(' '.join(match.groups()), '%d %B %Y').date().isoformat()


def date_end(label):
    return meeting_date(re.sub(r'^.*?[-–—]\s*', '', label))


def meeting_papers(markup, meeting):
    sections = re.split(r'<span class="cmp-accordion__title">(.*?)</span>', markup, flags=re.S)
    items = []
    for title, section in zip(sections[1::2], sections[2::2]):
        title = plain(title)
        if re.match(r'^(administrative|private session|work in progress|oral update|\s*$)', title, re.I):
            continue
        papers = []
        for listing in re.findall(r'<ul\b[^>]*class="[^"]*__entity--papers[^"]*"[^>]*>(.*?)</ul>', section, re.S):
            for entry in re.findall(r'<li\b[^>]*>(.*?)</li>', listing, re.S):
                label = plain(entry)
                number = re.match(r'(?:Agenda\s+Paper\s+|AP\s*)(\d+[A-Z]?)\b', label, re.I)
                if not number:
                    continue
                link = re.search(r'<a\b[^>]*href="([^"]+)"', entry)
                kind = ('comment_letter_analysis' if re.search(r'comments?|feedback', label, re.I) else
                        'updated_wording' if re.search(r'wording', label, re.I) else
                        'initial_consideration' if re.search(r'initial', label, re.I) else 'staff_paper')
                papers.append({'documentTitle': label, 'apNumber': 'AP' + number[1].upper(),
                               'documentUrl': official(link[1]) if link else '', 'relationshipType': kind,
                               'meetingDate': meeting['date'], 'sourcePageUrl': meeting['url']})
        if papers or 'ifrs-cmp-agendaitem' in section:
            items.append({'title': title, 'standards': standards(title), 'papers': papers})
    return items


def calendar(group, history, today):
    group_url = f'/groups/{GROUPS[group]}/'
    panel = lazy_tab(page(group_url), 'meetings')
    picker = re.search(r'IFRS\.groupsMeetingPicker\("([^"]+)"\)', panel)
    if not picker:
        raise ValueError(f'{group} meeting calendar endpoint is missing')
    endpoint = picker[1] + '.model.json'
    years = json.loads(page(endpoint))['yearList']
    if not years:
        raise ValueError(f'{group} meeting calendar is empty')
    scanned = history.get('scannedYears', [])
    wanted = [int(y) for y in years if int(y) >= today.year - (1 if group == 'IFRIC' else 0)
              or (group == 'IFRIC' and int(y) not in scanned)]
    entries = {}
    for year in wanted:
        result = json.loads(page(endpoint + '?' + urlencode({'year': year, 'projectTagId': 'all'})))
        for row in result['resultsList']:
            fragment = row['pathToExpFragmentHtml']
            tail = re.search(r'/meetings/_(.+?)/master\.html$', fragment)
            if not tail:
                raise ValueError(f'Unrecognized {group} meeting path: {fragment}')
            label = row['eventDateRange']
            url = BASE + '/news-and-events/calendar/' + tail[1] + '/'
            entries[url] = {'group': group, 'date': meeting_date(label), 'endDate': date_end(label),
                            'url': url, 'fragment': fragment}
    previous = {item['url']: item for item in history.get('meetings', []) if item['group'] == group}
    current_month = today.replace(day=1).isoformat()

    def load(meeting):
        url = meeting['url']
        cached = previous.get(url)
        if cached and cached.get('topics') and meeting['date'] < f'{today.year - 1}-01-01':
            return cached
        if group == 'IASB' and meeting['endDate'] < current_month:
            return None
        if meeting['date'] > today.isoformat() and (date.fromisoformat(meeting['date']) - today).days > 65:
            return None
        try:
            markup = page(meeting['fragment'])
        except HTTPError as error:
            if error.code != 404:
                raise
            markup = page(url)
        return {**meeting, 'topics': meeting_papers(markup, meeting)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for result in pool.map(load, sorted(entries.values(), key=lambda item: item['date'], reverse=True)):
            if result:
                previous[result['url']] = result
    return list(previous.values()), sorted(set(scanned + wanted))


def work_plan():
    endpoint = re.search(r'data-url="([^"]+projListData[^" ]+)"', page(PLAN))
    if not endpoint:
        raise ValueError('Work plan endpoint missing')
    rows = json.loads(page(html.unescape(endpoint[1])))
    if not isinstance(rows, list) or not any(row.get('projectTypeAbbr') == 'AQ' for row in rows):
        raise ValueError('Unexpected empty work plan')
    return [row for row in rows if 'Active' in (row.get('projectStatusList') or [])
            and (row.get('accountingFilter') or row.get('projectTypeAbbr') == 'AQ')]


def project_context(projects):
    def excerpt(project):
        url = official(project['projectPageUri'])
        try:
            content = page(url)
        except (OSError, ValueError) as error:
            print(f'Warning: project details unavailable: {url}: {error}')
            return url, ''
        stage = re.search(r'<h[1-4][^>]*>\s*Current stage\s*</h[1-4]>(.*?)(?:<h[1-4]\b|</div>\s*</div>)', content, re.S | re.I)
        if not stage:
            return url, ''
        paragraphs = [plain(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', stage[1], re.S)]
        return url, next((p for p in paragraphs if 50 <= len(p) <= 500), '')

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(excerpt, projects))


def committee_updates(today, cached):
    links = set(re.findall(r'href="([^\"]*/updates/ifric/\d{4}/[^\"]+)"', page(UPDATES)))
    links = sorted(set(official(link) for link in links))
    if not links:
        raise ValueError('No recent IFRIC Updates found')
    outcomes = {}

    def parse(url):
        if url in cached and int(url.split('/ifric/')[1][:4]) < today.year - 1:
            return url, cached[url]
        markup = page(url)
        month_match = re.search(r'ifric-update-[^/]*?(' + MONTH.lower() + r')-(\d{4})', url)
        month, year = month_match.groups() if month_match else ('January', re.search(r'/ifric/(\d{4})/', url)[1])
        update_date = datetime.strptime(f'1 {month.title()} {year}', '%d %B %Y').date().isoformat()
        modern = 'ifrs-cmp-iasbupdate__grouptitle' in markup
        groups = re.split(r'<h2 class="ifrs-cmp-iasbupdate__grouptitle">(.*?)</h2>' if modern else r'<h2[^>]*>(.*?)</h2>', markup, flags=re.S)
        entries = []
        for heading, group in zip(groups[1::2], groups[2::2]):
            label = plain(heading).lower()
            stage = ('final' if 'addendum' in label or re.fullmatch(r'committee[’\']s agenda decisions', label) else 'tentative' if 'tentative agenda' in label else
                     'pending-board' if 'consideration' in label and 'iasb' in label else '')
            heading_pattern = (r'<h3 class="ifrs-cmp-iasbupdate__h3-updatetitle"[^>]*id="([^"]+)"[^>]*>(.*?)</h3>' if modern
                               else r'<h3[^>]*>\s*<a[^>]*id="([^"]+)"[^>]*></a>(.*?)</h3>')
            subjects = re.split(heading_pattern, group, flags=re.S)
            for anchor, title, body in zip(subjects[1::3], subjects[2::3], subjects[3::3]):
                title = plain(title)
                deadline = re.search(rf'open for comment until\s+(\d{{1,2}} (?:{MONTH}) \d{{4}})', plain(body), re.I)
                text = next((plain(p) for p in re.findall(r'<p(?:\s[^>]*)?>(.*?)</p>', body, re.S)
                             if re.search(r'(?:received a request|request asked|considered feedback)', plain(p), re.I)), '')
                entries.append({'title': title, 'stage': stage, 'url': url + '#' + anchor, 'excerpt': text[:480],
                                'date': update_date,
                                'commentDate': meeting_date(deadline[1].title()) if deadline else '',
                                'decisionText': plain(re.split(r'</article>|class="share|Your privacy', body, maxsplit=1)[0])[:11000] if stage == 'final' else ''})
        return url, entries

    by_url = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for url, entries in pool.map(parse, links):
            by_url[url] = entries
            for item in entries:
                outcomes.setdefault(topic_key(item['title']), []).append(item)
    for entries in outcomes.values():
        entries.sort(key=lambda item: (item['date'], item['stage'] == 'final'))
    return outcomes, by_url


def add_historical_decisions(decisions, updates, previous):
    known = {topic_key(row['title']) for row in decisions}
    def canonical(value):
        return re.sub(r's\b', '', value).replace(' ', '')
    known_words = {canonical(key) for key in known}
    old = {item['sourceUrl']: item for item in previous}
    for key, entries in updates.items():
        if not key or canonical(key) in known_words:
            continue
        words = set(key.split())
        if any(len(words) >= 4 and (words <= set(other.split()) or set(other.split()) <= words)
               and len(words ^ set(other.split())) <= 2 for other in known):
            continue
        for entry in entries:
            body = entry['decisionText']
            if not re.search(r'(?:not to add|not be added|not to take|not to include|not to develop|would not add)', body, re.I):
                continue
            titled = re.split(r'\s*(?:[—–-]|\()\s*Agenda Paper', entry['title'], flags=re.I)[0].strip()
            tags = standards(titled)
            decisions.append({**old.get(entry['url'], {}), 'id': 'historical-' + stable_id(entry['url']), 'title': titled,
                              'sourceUrl': entry['url'], 'publishedAt': entry['date'], 'datePrecision': 'month',
                              'lastChangedAt': entry['date'], 'standards': tags, 'standard': tags[0] if tags else '',
                              'fullText': body, 'archiveOnly': True, 'volume': 'IFRIC Update', 'tags': ['agenda decision']})
    return sorted(decisions, key=lambda row: (row['publishedAt'], row['title']), reverse=True)


def stage_for_plan(project, today):
    comment = project.get('openForComment') or {}
    deadline = datetime.fromtimestamp(comment['finishDateTime'] / 1000, timezone.utc).date().isoformat() if comment.get('finishDateTime') else ''
    if deadline and deadline >= today.isoformat():
        return 'consultation', deadline
    milestone = (project.get('nextMilestoneMeetingTitle') or '').lower()
    if 'agenda decision feedback' in milestone:
        return 'tentative', ''
    if milestone == 'agenda decision':
        return 'pending-board', ''
    return 'active', ''


def local_date():
    try:
        return datetime.now(ZoneInfo('Asia/Jerusalem')).date()
    except ZoneInfoNotFoundError:
        return date.today()


def paper_index(data, meetings, updates):
    return PaperIndex(meetings, updates, read_json(data / 'ifric-paper-overrides.json', {}))


def write_json(path, payload):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def backfill_papers(data, decisions_path, decisions, history):
    index = paper_index(data, history['meetings'], (entry for rows in history['updateCache'].values() for entry in rows))
    before = sum(bool(decision.get('relatedPapers')) for decision in decisions)
    for decision in decisions:
        decision['relatedPapers'] = index.for_decision(decision, decision.get('relatedPapers', []))
    after = sum(bool(decision['relatedPapers']) for decision in decisions)
    write_json(decisions_path, decisions)
    print(f'{after}/{len(decisions)} decisions with preceding papers (previously {before}); no network requests.')


def build_monitor(data, output, decisions_path, today, decisions, committees, board, scanned, projects, updates, contexts, history, translate):
    old_tracker = read_json(data / 'ifric-tracker.json', {}).get('items', [])
    by_title = {}
    for meeting in committees + board:
        for item in meeting['topics']:
            by_title.setdefault((meeting['group'], topic_key(item['title'])), []).append((meeting, item))
    final_keys = {topic_key(row['title']) for row in decisions}

    def papers_for(group, title, through='9999', related_standards=()):
        papers = {}
        for meeting, subject in by_title.get((group, topic_key(title)), []):
            if related_standards and subject['standards'] and not set(related_standards).intersection(subject['standards']):
                continue
            if meeting['date'] <= through:
                for paper in subject['papers']:
                    papers[paper['documentUrl'] or (meeting['url'], paper['apNumber'])] = paper
        return sorted(papers.values(), key=lambda paper: (paper['meetingDate'], paper['apNumber']))

    editorial = read_json(data / 'ifrs-editorial.json', {})
    titles = read_json(data / 'ifric-titles-he.json', {})
    linked_papers = paper_index(data, committees, (entry for entries in updates.values() for entry in entries))
    translation_queue = []
    for decision in decisions:
        key = topic_key(decision['title'])
        decision.update(editorial.get('history', {}).get(key, {}))
        curated = next((item for item in old_tracker if item.get('finalAgendaDecisionUrl') == decision['sourceUrl']
                        or (topic_key(item['topicTitleEn']) == key and item.get('standard') in decision['standards'])), {})
        decision['relatedPapers'] = linked_papers.for_decision(
            decision, [*decision.get('relatedPapers', []), *curated.get('relatedPapers', [])])
        outcomes = [item for item in updates.get(key, []) if item['date'] <= decision['publishedAt']]
        candidates = [item for item in outcomes if item['stage'] in ('final', 'pending-board')]
        decision['ifricUpdateUrl'] = candidates[-1]['url'] if candidates else curated.get('ifricUpdateUrl', '')
        tentative = [item for item in outcomes if item['stage'] == 'tentative']
        decision['tentativeAgendaDecisionUrl'] = tentative[-1]['url'] if tentative else curated.get('tentativeAgendaDecisionUrl', '')
        decision['needsReview'] = any(paper.get('needsReview') for paper in decision['relatedPapers'])
        if title_he := titles.get(urlsplit(decision['sourceUrl']).path):
            if not decision.get('topicTitleHe') or 'topicTitleHe' in decision.get('automaticHe', {}):
                decision['topicTitleHe'] = title_he
                decision.get('automaticHe', {}).pop('topicTitleHe', None)
        if summary := editorial.get('decisions', {}).get(key):
            if not decision.get('summaryHe') or 'summaryHe' in decision.get('automaticHe', {}):
                decision['summaryHe'] = summary
                decision.get('automaticHe', {}).pop('summaryHe', None)
        digest = fingerprint(decision['fullText'])
        excerpt = decision_excerpt(decision['fullText'])
        if decision.get('reviewedSourceHash', digest) != digest:
            decision['needsReview'] = True
            translation_queue.append((decision, 'summaryProposalHe', excerpt))
        elif decision.get('summaryHe') and 'summaryHe' not in decision.get('automaticHe', {}):
            decision['reviewedSourceHash'] = digest
        translation_queue.extend(((decision, 'topicTitleHe', decision['title']),
                                  (decision, 'summaryHe', excerpt)))

    active = []
    by_project = {}
    for project in projects:
        title = project['projectPageTitle']
        key = topic_key(title)
        group = 'IFRIC' if project['projectTypeAbbr'] == 'AQ' else 'IASB'
        if group == 'IFRIC' and key in final_keys:
            continue
        url = official(project['projectPageUri'])
        stage, deadline = stage_for_plan(project, today)
        outcomes = updates.get(key, []) if group == 'IFRIC' else []
        outcome = next((item for item in reversed(outcomes) if item['stage']), outcomes[-1] if outcomes else {})
        if stage == 'active' and outcome.get('stage') in ('tentative', 'pending-board'):
            stage = outcome['stage']
        papers = papers_for(group, title)
        comment = project.get('openForComment') or {}
        item = {'id': 'project-' + stable_id(url), 'topicTitleEn': title, 'group': group,
                'standards': standards(project.get('standardTags'), title), 'sourceUrl': url,
                'stage': stage, 'nextMilestone': project.get('nextMilestoneMeetingTitle') or '',
                'milestoneDate': (project.get('nextMilestoneDueDate') or '')[:10],
                'commentDate': deadline or outcome.get('commentDate', ''),
                'tentativeAgendaDecisionUrl': (official(comment['path']) if comment.get('path') else outcome.get('url', '')) if group == 'IFRIC' and (comment.get('path') or outcome.get('stage') == 'tentative') else '',
                'consultationUrl': official(comment['path']) if comment.get('path') else '',
                'ifricUpdateUrl': outcome.get('url', ''), 'sourceExcerpt': outcome.get('excerpt') or contexts.get(url, ''), 'relatedPapers': papers}
        active.append(item)
        by_project[group, key] = item

    for key, outcomes in updates.items():
        outcome = next((item for item in reversed(outcomes) if item['stage']), None)
        if not outcome or outcome['stage'] not in ('tentative', 'pending-board') or key in final_keys or ('IFRIC', key) in by_project:
            continue
        if (today - date.fromisoformat(outcome['date'])).days > 180:
            continue
        title = re.split(r'[—–-]\s*Agenda Paper', outcome['title'], flags=re.I)[0].strip()
        deadline = outcome['commentDate']
        item = {'id': 'update-topic-' + stable_id(key), 'group': 'IFRIC', 'topicTitleEn': title,
                'standards': standards(title), 'sourceUrl': outcome['url'], 'ifricUpdateUrl': outcome['url'],
                'stage': 'consultation' if deadline >= today.isoformat() else outcome['stage'], 'commentDate': deadline,
                'tentativeAgendaDecisionUrl': outcome['url'] if outcome['stage'] == 'tentative' else '',
                'sourceExcerpt': outcome['excerpt'], 'relatedPapers': papers_for('IFRIC', title)}
        active.append(item)
        by_project['IFRIC', key] = item

    scheduled = []
    latest_dates = {group: max((m['date'] for m in meetings if m['endDate'] < today.isoformat() and m['topics']), default='')
                    for group, meetings in (('IFRIC', committees), ('IASB', board))}
    for meeting in committees + board:
        group = meeting['group']
        if meeting['date'] < date(today.year, 1, 1).isoformat():
            continue
        for subject in meeting['topics']:
            title = subject['title']
            key = topic_key(title)
            project = by_project.get((group, key), {}) or (by_project.get(('IASB', key), {}) if group == 'IFRIC' else {})
            if meeting['endDate'] < today.isoformat() and meeting['date'] != latest_dates[group]:
                continue
            if group == 'IFRIC' and key in final_keys:
                continue
            papers = subject['papers']
            published = next((paper['documentUrl'] for paper in papers if paper['documentUrl']), '')
            scheduled.append({**project, 'id': 'meeting-' + stable_id(meeting['url'] + '|' + key),
                              'topicTitleEn': title, 'group': group, 'standards': subject['standards'] or project.get('standards', []),
                              'stage': 'scheduled' if meeting['endDate'] >= today.isoformat() else project.get('stage', 'discussed'),
                              'meetingDate': meeting['date'], 'meetingEndDate': meeting['endDate'], 'meetingUrl': meeting['url'],
                              'sourceUrl': project.get('sourceUrl') or meeting['url'], 'documentUrl': published,
                              'apNumber': ' / '.join(dict.fromkeys(paper['apNumber'] for paper in papers)),
                              'relatedPapers': papers, 'paperPending': not papers or any(not paper['documentUrl'] for paper in papers),
                              'sourceExcerpt': project.get('sourceExcerpt', '')})

    for entry in editorial.get('announcedProjects', []):
        if not any(topic_key(item['topicTitleEn']) == topic_key(entry['topicTitleEn']) for item in active):
            if today <= date.fromisoformat(entry['showThrough']):
                active.append(entry)

    old_by_id = {item['id']: item for item in history.get('active', []) + history.get('scheduled', [])}
    paper_contexts = {item['documentUrl']: item['sourceExcerpt'] for item in history.get('scheduled', [])
                      if item.get('documentUrl') and len(item.get('sourceExcerpt', '')) >= 60}
    extractor = pdf_extractor()
    needs_context = {item['documentUrl'] for item in scheduled if item.get('documentUrl')
                     and len(item.get('sourceExcerpt', '')) < 60 and item['documentUrl'] not in paper_contexts
                     and topic_key(item['topicTitleEn']) not in editorial.get('discussions', {})}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        urls = sorted(needs_context)
        paper_contexts.update(zip(urls, pool.map(lambda url: staff_context(url, extractor), urls)))
    changes = list(history.get('changes', []))
    if history.get('changesVersion') != 2:
        changes = []
    bootstrap_feed = history.get('changesVersion') != 2
    for item in active + scheduled:
        old = old_by_id.get(item['id'])
        for field in ('topicTitleHe', 'summaryHe', 'automaticHe'):
            if old and field in old and field not in item:
                item[field] = old[field]
        if copy := editorial.get('discussions', {}).get(topic_key(item['topicTitleEn'])):
            for field, value in zip(('topicTitleHe', 'summaryHe', 'staffViewHe'), copy):
                if not item.get(field) or field in item.get('automaticHe', {}):
                    item[field] = value
                    item.get('automaticHe', {}).pop(field, None)
        summary_source = item.get('sourceExcerpt', '')
        if len(summary_source) < 60 and item.get('documentUrl') in paper_contexts:
            summary_source = paper_contexts[item['documentUrl']]
            item['sourceExcerpt'] = summary_source
        if len(summary_source) < 60:
            summary_source = ''
        translation_queue.extend(((item, 'topicTitleHe', item['topicTitleEn']),
                                  (item, 'summaryHe', summary_source)))
        fields = ('stage', 'nextMilestone', 'milestoneDate', 'commentDate', 'sourceUrl', 'relatedPapers', 'meetingDate')
        changed_fields = [field for field in fields if old and old.get(field) != item.get(field)]
        item['lastChangedAt'] = today.isoformat() if not old or changed_fields else old['lastChangedAt']
        if (bootstrap_feed and item.get('stage') in ('scheduled', 'announced')) or (not bootstrap_feed and (not old or changed_fields)):
            new_paper = old and set(p.get('documentUrl') for p in item.get('relatedPapers', []) if p.get('documentUrl')) - set(
                p.get('documentUrl') for p in old.get('relatedPapers', []) if p.get('documentUrl'))
            changes.append({'id': stable_id(item['id'] + today.isoformat() + str(changed_fields)),
                            'itemId': item['id'], 'topicTitleEn': item['topicTitleEn'], 'group': item['group'],
                            'changedAt': today.isoformat(), 'changeType': 'new' if not old or bootstrap_feed else 'paper' if new_paper else 'updated',
                            'sourceUrl': item.get('documentUrl') or item['sourceUrl']})

    previous_decisions = {item['sourceUrl']: item for item in read_json(decisions_path, [])}
    for item in decisions:
        old = previous_decisions.get(item['sourceUrl'])
        if not old or item['fullText'] != old.get('fullText') or item['title'] != old.get('title') or (bootstrap_feed and item['publishedAt'] >= f'{today.year}-01-01'):
            changes.append({'id': stable_id(item['id'] + item['lastChangedAt']), 'itemId': item['id'],
                            'topicTitleEn': item['title'], 'group': 'IFRIC', 'changedAt': item['lastChangedAt'],
                            'changeType': 'final' if not old or bootstrap_feed else 'updated', 'sourceUrl': item['sourceUrl']})

    translation_issue = ''
    try:
        localize(translation_queue, ROOT / '.cache/ifrs-he-model', translate)
    except Exception as error:
        translation_issue = 'translation-unavailable'
        print(f'Warning: translation queued for retry: {error}')

    snapshot = {'generatedAt': today.isoformat(), 'archiveCount': sum(not item.get('archiveOnly') for item in decisions), 'scannedYears': scanned,
                'changesVersion': 2, 'updateCache': history['updateCache'],
                'translationIssue': translation_issue,
                'active': active, 'scheduled': scheduled,
                'changes': sorted({item['id']: item for item in changes}.values(), key=lambda item: item['changedAt'], reverse=True)[:200],
                'meetings': sorted(committees + board, key=lambda item: (item['date'], item['url']))}
    for path, payload in ((decisions_path, decisions), (output, snapshot)):
        write_json(path, payload)
    print(f'{snapshot["archiveCount"]} catalogue documents, {len(decisions)} total entries, '
          f'{sum(bool(row["relatedPapers"]) for row in decisions)} with preceding papers, '
          f'{len(active)} active projects, {len(scheduled)} meeting topics, {len(committees) + len(board)} meetings.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--today', type=date.fromisoformat, default=local_date())
    parser.add_argument('--skip-translation', action='store_true')
    parser.add_argument('--backfill-papers', action='store_true', help='Relink papers using local snapshots only')
    args = parser.parse_args()
    data, today = args.data_dir, args.today
    decisions_path = data / 'ifric.json'
    output = data / 'ifrs-monitor.json'
    history = read_json(output, {})
    previous = read_json(decisions_path, [])
    if args.backfill_papers:
        backfill_papers(data, decisions_path, previous, history)
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {
            'archive': pool.submit(lambda: archive_rows(lazy_tab(page(ARCHIVE), 'agenda-decisions'))),
            'ifric': pool.submit(calendar, 'IFRIC', history, today),
            'iasb': pool.submit(calendar, 'IASB', history, today),
            'plan': pool.submit(work_plan),
            'updates': pool.submit(committee_updates, today, history.get('updateCache', {})),
        }
        projects = jobs['plan'].result()
        context_job = pool.submit(project_context, projects)
        decisions = collect_decisions(jobs['archive'].result(), previous, today)
        committees, scanned = jobs['ifric'].result()
        board, _ = jobs['iasb'].result()
        updates, update_cache = jobs['updates'].result()
        contexts = context_job.result()
    decisions = add_historical_decisions(decisions, updates, previous)
    history['updateCache'] = update_cache
    build_monitor(data, output, decisions_path, today, decisions, committees, board, scanned, projects, updates, contexts, history, not args.skip_translation)


if __name__ == '__main__':
    main()
