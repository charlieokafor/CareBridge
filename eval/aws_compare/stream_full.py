# All 355 clips through the app's planned path: real-time Transcribe, clip fed fast, language known.
# Usage: python stream_full.py SET_DIR OUT.json [vocab]   (SET_DIR has meta.json + mix/)   (vocab = use the carebridge-<lang> custom vocabularies)
import sys, time, wave, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/opt/cb-dev')
from aws_transcribe import transcribe_pcm
D=sys.argv[1]; meta=json.load(open(f'{D}/meta.json')); OUT=sys.argv[2]; VOC=len(sys.argv)>3
LOC={"uk":"uk-UA","pl":"pl-PL","ro":"ro-RO","ru":"ru-RU","ar":"ar-SA"}
def one(k):
    m=meta[k]; lc=LOC.get(m['lang']) or ('en-US' if m.get('kind')=='fleurs' else 'en-IE')
    voc={lc: f"carebridge-{lc}"} if VOC else None
    pcm=wave.open(f'{D}/mix/{k}.wav').readframes(10**8); t=time.time()
    for a in range(4):
        try: r=transcribe_pcm(pcm, language_code=lc, vocabularies=voc, timeout=40); break
        except Exception as e: err=str(e); time.sleep(3+a*3)
    else: return k, {'text':'','error':err}
    return k, {'text': r['text'], 'lang': m['lang'], 'conf': r['confidence'], 's': round(time.time()-t,2)}
out={}
with ThreadPoolExecutor(6) as ex:
    for k,v in ex.map(one, sorted(meta)): out[k]=v
json.dump(out, open(OUT,'w'), ensure_ascii=False); print('done', len(out), sum('error' in v for v in out.values()), 'errors')
