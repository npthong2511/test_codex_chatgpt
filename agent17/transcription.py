"""Bounded Vietnamese STT; no substitution dictionary for misheard words."""
import re

def transcribe_vi(create, wav_path, model, events=None):
    events = events if events is not None else []
    # Do not seed STT with the pending question: weak audio can echo that prompt.
    text = ''
    for attempt in range(2):
        with wav_path.open('rb') as audio:
            result = create(model=model,file=audio,language='vi')
        text = (result.text or '').strip()
        events.append({'attempt':attempt+1,'text':text,'language':'vi'})
        if text and re.search(r'[0-9A-Za-zÀ-ỹ]',text):
            break
        # Retry the same audio once only for empty/non-Latin output. No invented replacement.
    return text


def has_transcript(text):
    """Nonempty speech candidates reach the model; script alone is not silence."""
    return any(char.isalpha() or char.isdigit() for char in (text or ''))
