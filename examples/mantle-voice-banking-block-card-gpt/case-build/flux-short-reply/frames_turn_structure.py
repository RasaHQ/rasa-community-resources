"""Summarise the TurnInfo messages saved in flux-short-reply-frames.jsonl.
Usage: python3 frames_turn_structure.py flux-short-reply-frames.jsonl
Messages after CloseStream are excluded, as in the replay. 'lost' = no Update with a transcript."""
import collections, json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
att = {r['attempt']: r for r in rows if r.get('kind') == 'attempt'}
msgs = collections.defaultdict(list)
for r in rows:
    if r.get('kind') == 'message' and not r['after_close_stream'] and r['message'].get('type') == 'TurnInfo':
        msgs[r['attempt']].append(r['message'])
def has_update(ms): return any(m['event'] == 'Update' and m['transcript'] for m in ms)
lost = [a for a, ms in msgs.items() if not has_update(ms)]
heard = [a for a, ms in msgs.items() if has_update(ms)]
print(f'attempts {len(att)}: lost (no Update with words) {len(lost)}, heard {len(heard)}')
def ev(a, name): return [m for m in msgs[a] if m['event'] == name]
print('lost: StartOfTurn audio_window_end', collections.Counter(tuple(round(m['audio_window_end'], 2) for m in ev(a, 'StartOfTurn')) for a in lost))
print('lost: EndOfTurn audio_window_end  ', collections.Counter(tuple(round(m['audio_window_end'], 2) for m in ev(a, 'EndOfTurn')) for a in lost))
print('lost: events from StartOfTurn to EndOfTurn', collections.Counter(
    tuple(m['event'] for m in msgs[a][[m['event'] for m in msgs[a]].index('StartOfTurn'):[m['event'] for m in msgs[a]].index('EndOfTurn') + 1]) for a in lost))
print('lost: StartOfTurn transcripts', collections.Counter(m['transcript'] for a in lost for m in ev(a, 'StartOfTurn')))
print('lost: EndOfTurn transcripts  ', collections.Counter(m['transcript'] for a in lost for m in ev(a, 'EndOfTurn')))
print('lost WAVs', collections.Counter(att[a]['wav'] for a in lost))
def rng(xs): return f'{min(xs):.4f} to {max(xs):.4f} (n={len(xs)})'
print('end_of_turn_confidence, EndOfTurn, lost      ', rng([m['end_of_turn_confidence'] for a in lost for m in ev(a, 'EndOfTurn')]))
print('end_of_turn_confidence, EndOfTurn, all       ', rng([m['end_of_turn_confidence'] for a in msgs for m in ev(a, 'EndOfTurn')]))
print('end_of_turn_confidence, Update with words    ', rng([m['end_of_turn_confidence'] for a in msgs for m in ev(a, 'Update') if m['transcript']]))
print('heard: attempts with an Update between StartOfTurn and EndOfTurn',
      sum('Update' in [m['event'] for m in msgs[a]][[m['event'] for m in msgs[a]].index('StartOfTurn'):[m['event'] for m in msgs[a]].index('EndOfTurn')] for a in heard), 'of', len(heard))
for a in (1, 32):
    print(f'attempt {a} (lead {att[a].get("lead_silence_s", "see replay")}):')
    for m in msgs[a]:
        if m['audio_window_end'] in (2.16, 2.4, 2.64) or round(m['audio_window_end'], 2) in (2.16, 2.4, 2.64):
            print(f"   window_end {m['audio_window_end']:.2f}  {m['event']:12s} transcript={m['transcript']!r:8s} end_of_turn_confidence={m['end_of_turn_confidence']}")
