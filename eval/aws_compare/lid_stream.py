# Amazon Transcribe real-time language identification (LID) on the language-detection clips
import sys, time, wave, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/opt/cb-dev')
from aws_transcribe import transcribe_pcm
meta=json.load(open('/opt/cb-dev/lidmeta.json'))
OPTS=["en-IE","uk-UA","ru-RU","pl-PL","ro-RO","ar-SA","fr-FR","de-DE","hi-IN","ko-KR","es-ES"]
def one(k):
    pcm=wave.open(f'/opt/cb-dev/lid/{k}.wav').readframes(10**8); t=time.time()
    for a in range(3):
        try: r=transcribe_pcm(pcm, language_options=OPTS, timeout=40); break
        except Exception as e: err=str(e); time.sleep(3)
    else: return k, {'error': err}
    return k, {'lang': r['languageCode'], 'scores': r['languageScores'], 'secs': round(time.time()-t,2)}
out={}
with ThreadPoolExecutor(10) as ex:
    for k,v in ex.map(one, sorted(meta)): out[k]=v; print(k, v.get('lang'), flush=True)
json.dump(out, open('/opt/cb-dev/lid_stream.json','w'))
