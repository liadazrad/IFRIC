import hashlib
import re
from pathlib import Path
import os
from urllib.request import urlopen


REVISION = '1faa63b92ac9daffeef092500695c160d6b37cc6'
MODEL = f'https://huggingface.co/manancode/opus-mt-en-he-ctranslate2-android/resolve/{REVISION}/'
FILES = ('config.json', 'source.spm', 'target.spm', 'shared_vocabulary.json', 'model.bin')
GLOSSARY = {
    'agenda decision': 'החלטת סדר יום', 'cash and cash equivalents': 'מזומנים ושווי מזומנים',
    'other comprehensive income': 'רווח כולל אחר', 'profit or loss': 'רווח והפסד',
    'non-controlling interests': 'זכויות שאינן מקנות שליטה', 'right-of-use asset': 'נכס זכות שימוש',
    'cash-generating unit': 'יחידה מניבת מזומנים', 'amortised cost': 'עלות מופחתת',
    'fair value': 'שווי הוגן', 'financial statements': 'דוחות כספיים', 'work plan': 'תוכנית העבודה',
    'carrying amount': 'ערך בספרים', 'recognition': 'הכרה', 'residual value': 'ערך שייר',
}


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def decision_excerpt(text):
    text = re.split(r'Copyright\s*©|© IFRS Foundation', text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r'Agenda Decision.{0,250}?Page \d+ of \d+(?: Agenda Decision)?', ' ', text)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text) if 22 < len(s) < 520]
    question = re.search(r'The (?:Committee|IFRIC) received a request[^.]{15,420}\.', text, re.I)
    detail = next((s for s in reversed(sentences) if re.search(
        r'(?:The (?:Committee|IFRIC) (?:observed|noted|concluded) that|Feedback suggest|Evidence gathered)', s, re.I)
        and not re.search(r'work plan|agenda\.?$|standard-setting project|sufficient guidance|adequate basis', s, re.I)), '')
    if not detail:
        detail = next((s for s in reversed(sentences) if re.search(r'(?:The (?:Committee|IFRIC) (?:agreed|decided|concluded|noted))', s, re.I)), '')
    intro = question[0] if question else next((s for s in sentences if re.search(r'The (?:Committee|IFRIC|request)', s, re.I)), '')
    if not intro and not detail:
        intro = next((s for s in sentences if not re.search(r'Copyright|all rights reserved|published by', s, re.I)), '')
    return ' '.join(dict.fromkeys(part for part in (intro, detail) if part))


def model_at(cache):
    import ctranslate2
    import sentencepiece

    cache.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        target = cache / filename
        if not target.is_file():
            temp = target.with_suffix('.download')
            with urlopen(MODEL + filename, timeout=90) as response, temp.open('wb') as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            os.replace(temp, target)
    source = sentencepiece.SentencePieceProcessor(model_file=str(cache / 'source.spm'))
    target = sentencepiece.SentencePieceProcessor(model_file=str(cache / 'target.spm'))
    engine = ctranslate2.Translator(str(cache), device='cpu', compute_type='int8', intra_threads=3)

    def translate(inputs):
        tokens = [source.encode(line, out_type=str) + ['</s>'] for line in inputs]
        rows = engine.translate_batch(tokens, beam_size=3, max_batch_size=12, max_decoding_length=220)
        results = [target.decode([token for token in row.hypotheses[0] if token not in ('<pad>', '</s>')]) for row in rows]
        for index, value in enumerate(results):
            for wrong, right in {'דוחות פיננסיים': 'דוחות כספיים', 'ערך הוגן': 'שווי הוגן',
                                 'רווח או הפסד': 'רווח והפסד', 'החלטת סדר היום': 'החלטת סדר יום',
                                 'זרמי מזומנים': 'תזרימי מזומנים', 'פיקדון ביקוש': 'פיקדון לפי דרישה',
                                 'מזומנים מקבילים': 'שווי מזומנים', 'עמדה פיננסית': 'מצב כספי'}.items():
                value = value.replace(wrong, right)
            results[index] = value.strip()
        return results

    return translate


def localize(records, cache, use_model):
    pending = {}
    for item, field, source in records:
        if not source or (item.get(field) and field not in item.get('automaticHe', {})):
            continue
        digest = fingerprint('he-v2\n' + source)
        if item.get('automaticHe', {}).get(field) == digest and item.get(field):
            continue
        pending.setdefault(source, []).append((item, field, digest))
    if not pending or not use_model:
        return
    translate = model_at(Path(cache))
    inputs = list(pending)
    for i in range(0, len(inputs), 48):
        chunk = inputs[i:i + 48]
        for source, value in zip(chunk, translate(chunk)):
            value = GLOSSARY.get(source.casefold(), value)
            if not re.search('[\u05d0-\u05ea]{2}', value) or re.search(r'<unk>|_BAR_|[\ufffd]', value):
                continue
            for item, field, digest in pending[source]:
                item[field] = value
                item.setdefault('automaticHe', {})[field] = digest
    print(f'Processed {len(pending)} distinct texts for automatic Hebrew translation.')
