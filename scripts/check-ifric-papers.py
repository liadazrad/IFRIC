import json
from pathlib import Path
import unittest

from ifric_papers import PaperIndex, ap_numbers, last_paper_date


ROOT = Path(__file__).resolve().parent.parent


def load(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8-sig'))


class PaperMatchingTests(unittest.TestCase):
    def test_agenda_paper_ranges(self):
        self.assertEqual(ap_numbers('Topic (IAS 27)—Agenda Papers 4–4C'), {'AP4', 'AP4A', 'AP4B', 'AP4C'})
        self.assertEqual(ap_numbers('Topic (IAS 27)—Agenda Paper 4B'), {'AP4B'})

    def test_reprint_uses_original_decision_date(self):
        decision = {'title': 'Demand Deposits (IAS 7)', 'publishedAt': '2025-11-01',
                    'fullText': 'Published in April 2022 Updated in January 2026 to replace references'}
        self.assertEqual(last_paper_date(decision), '2022-04-30')

    def test_ambiguous_ap_is_not_linked(self):
        decision = {'title': 'Topic (IAS 27)', 'publishedAt': '2024-02-24',
                    'sourceUrl': 'https://www.ifrs.org/decision.pdf'}

        def meeting(day, title, file):
            return {'group': 'IFRIC', 'date': day, 'topics': [{
                'title': title, 'papers': [{'apNumber': 'AP4', 'meetingDate': day,
                                            'documentUrl': 'https://www.ifrs.org/' + file}]}]}

        update = {'title': 'Topic (IAS 27)—Agenda Paper 4', 'date': '2024-02-01'}
        first = meeting('2024-02-02', 'First item (IAS 27)', 'first.pdf')
        other = meeting('2024-02-15', 'Other item (IAS 27)', 'other.pdf')
        self.assertEqual(PaperIndex([first, other], [update]).for_decision(decision), [])
        future = meeting('2024-02-25', 'Topic (IAS 27)', 'future.pdf')
        different_standard = meeting('2024-02-10', 'Other item (IFRS 9)', 'ifrs9.pdf')
        links = PaperIndex([first, future, different_standard], [update]).for_decision(decision)
        self.assertEqual([paper['documentUrl'] for paper in links], ['https://www.ifrs.org/first.pdf'])

    def test_shared_agenda_item_keeps_distinct_ias27_papers(self):
        decisions = load('ifric.json')
        monitor = load('ifrs-monitor.json')
        index = PaperIndex(monitor['meetings'], (entry for rows in monitor['updateCache'].values() for entry in rows),
                           load('ifric-paper-overrides.json'))
        for name, numbers in [('Step acquisition', {'AP6B', 'AP4B'}), ('Partial disposal', {'AP6A', 'AP4A'})]:
            decision = next(d for d in decisions if d['title'].endswith(name + ' (IAS 27)'))
            expected = index.for_decision(decision)
            self.assertEqual({paper['apNumber'] for paper in expected}, numbers)
            self.assertEqual(decision['relatedPapers'], expected)


if __name__ == '__main__':
    unittest.main()
