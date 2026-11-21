"""Link final agenda decisions to papers listed in existing IFRIC meeting records."""

import calendar
from datetime import datetime
import re
from urllib.parse import urlsplit


STANDARD = r'\b(?:IAS|IFRS|IFRIC|SIC)[ -]+\d+[A-Z]?\b'
MONTHS = r'January|February|March|April|May|June|July|August|September|October|November|December'


def topic_key(title):
    title = re.split(r'\s*[–—-]\s*(?:updated\b|agenda papers?\b)', title, maxsplit=1, flags=re.I)[0]
    title = re.sub(r'^' + STANDARD + r'[^–—]*[–—]\s*', '', title, flags=re.I)
    title = re.sub(r'\(\s*' + STANDARD + r'[^()]*\)|\[\s*' + STANDARD + r'[^\[\]]*\]', '', title, flags=re.I)
    title = re.sub(r'\s+' + STANDARD + r'\s*$', '', title, flags=re.I)
    title = re.sub(r'\binvestments in a subsidiary\b', 'investment in a subsidiary', title, flags=re.I)
    return ''.join(re.findall('[a-z0-9]+', title.lower()))


def month_end(month):
    year, number = map(int, month.split('-'))
    return f'{month}-{calendar.monthrange(year, number)[1]:02d}'


def last_paper_date(decision, use_publication_month=False):
    published = decision['publishedAt']
    heading = decision.get('fullText', '')[:550]
    if re.search(r'\bupdated in\b', decision['title'] + ' ' + heading, re.I):
        original = re.search(r'\bPublished (?:by (?:the )?IFRS Interpretations Committee )?in ('
                             + r'(?:' + MONTHS + r') \d{4})\b', heading, re.I)
        if original:
            return month_end(datetime.strptime(original[1], '%B %Y').strftime('%Y-%m'))
    if use_publication_month or decision.get('datePrecision') == 'month' or published.endswith('-01'):
        # Older catalogue dates often use day 01 for an issue specified only by month.
        return month_end(published[:7])
    return published


def ap_numbers(title):
    match = re.search(r'\bagenda papers?\s+([0-9]+[A-Z]?(?:\s*[-–—]\s*[0-9]+[A-Z]?)?)', title, re.I)
    if not match:
        return set()
    bounds = re.split(r'\s*[-–—]\s*', match[1].upper())
    if len(bounds) == 2:
        first = re.fullmatch(r'(\d+)([A-Z]?)', bounds[0])
        last = re.fullmatch(r'(\d+)([A-Z]?)', bounds[1])
        if first[1] == last[1] and last[2]:
            return {'AP' + first[1] + chr(code)
                    for code in range(ord(first[2] or 'A'), ord(last[2]) + 1)} | {'AP' + bounds[0]}
        if not first[2] and not last[2] and 0 <= int(last[1]) - int(first[1]) <= 10:
            return {f'AP{i}' for i in range(int(first[1]), int(last[1]) + 1)}
    return {'AP' + bound for bound in bounds}


def standard_codes(values):
    return {re.sub(r'[- ]+', ' ', code.upper()) for value in values
            for code in re.findall(STANDARD, value or '', flags=re.I)}


class PaperIndex:
    def __init__(self, meetings, updates, overrides=None):
        self.by_title = {}
        self.by_month = {}
        self.updates = {}
        self.overrides = {topic_key(title): entry for title, entry in (overrides or {}).items()}
        for meeting in meetings:
            if meeting['group'] != 'IFRIC':
                continue
            for topic in meeting['topics']:
                if not topic['papers']:
                    continue
                row = (meeting['date'], topic)
                self.by_title.setdefault(topic_key(topic['title']), []).append(row)
                self.by_month.setdefault(meeting['date'][:7], []).append(row)
        for update in updates:
            if numbers := ap_numbers(update['title']):
                self.updates.setdefault(topic_key(update['title']), []).append((update, numbers))

    def for_decision(self, decision, existing=()):
        key = topic_key(decision['title'])
        if not key:
            return []
        overrides = self.overrides.get(key, {})
        cutoff = last_paper_date(decision, overrides.get('usePublicationMonth', False))
        earliest = f'{int(cutoff[:4]) - 4:04d}{cutoff[4:]}'
        titles = {key, *(topic_key(title) for title in overrides.get('titles', []))}
        standards = standard_codes([decision['title'], *(decision.get('standards') or [decision.get('standard')])])
        results = {}

        def compatible(topic):
            codes = standard_codes([topic['title'], *topic.get('standards', [])])
            return not (standards and codes and standards.isdisjoint(codes))

        def attach(paper, evidence):
            link = paper.get('documentUrl', '')
            url = urlsplit(link)
            if (url.scheme != 'https' or url.netloc != 'www.ifrs.org' or not paper.get('meetingDate')
                    or paper['meetingDate'] > cutoff or link == decision['sourceUrl']
                    or paper.get('relationshipType') in ('final_agenda_decision', 'ifric_update', 'tentative_agenda_decision')):
                return
            results.setdefault(link, {**paper, 'matchBasis': evidence})

        for title in sorted(titles, key=lambda candidate: (candidate != key, candidate)):
            for date, topic in self.by_title.get(title, []):
                if earliest <= date <= cutoff and compatible(topic):
                    for paper in topic['papers']:
                        attach(paper, 'meeting_topic' if title == key else 'reviewed_title')

            # AP numbers repeat. Match a unique paper group within the Update's month.
            for update, numbers in self.updates.get(title, []):
                month = update['date'][:7]
                if not earliest[:7] <= month <= cutoff[:7]:
                    continue
                evidence_codes = standard_codes([update['title']])
                if standards and evidence_codes and standards.isdisjoint(evidence_codes):
                    continue
                for number in numbers:
                    matches = [(topic_key(topic['title']), [p for p in topic['papers'] if p['apNumber'] == number])
                               for date, topic in self.by_month.get(month, [])
                               if date <= cutoff and compatible(topic) and any(p['apNumber'] == number for p in topic['papers'])]
                    exact = [papers for name, papers in matches if name in titles]
                    candidates = exact or [papers for _, papers in matches]
                    if len(candidates) == 1:
                        for paper in candidates[0]:
                            attach(paper, 'ifric_update')

        for selection in overrides.get('papers', []):
            if selection.get('decisionMonth', decision['publishedAt'][:7]) != decision['publishedAt'][:7]:
                continue
            date = selection['date']
            title = topic_key(selection['title'])
            for meeting_date, topic in self.by_month.get(date[:7], []):
                if meeting_date == date and title == topic_key(topic['title']) and compatible(topic):
                    for paper in topic['papers']:
                        if paper['apNumber'] in selection['ap']:
                            attach(paper, 'reviewed_agenda')

        for paper in existing:
            attach(paper, paper.get('matchBasis', 'existing'))
        return sorted(results.values(), key=lambda paper: (paper['meetingDate'], paper['apNumber'], paper['documentUrl']))
