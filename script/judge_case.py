"""Judge one replay-verified case with bounded memory and durable raw responses."""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

from judge_packet_codec import compact
import judge_protocol


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(compact(value) + '\n')
    temporary.replace(path)


def image_parts(packet, delivery_index, protocol):
    # Include precisely the unique evidence images the candidate actually saw,
    # reconstructed at recorded transmitted dimensions/SHA. No hidden images.
    import evidence_images
    import run_current_english_gemini as core
    import resume_with_image_budget as adaptation
    from PIL import Image
    entries = json.loads((judge_protocol.BUNDLE / 'data/current-counterfactual-manifest.json').read_text())['episodes']
    entries += json.loads((judge_protocol.BUNDLE / 'data/current-english-manifest.json').read_text())['episodes']
    entry = next(entry for entry in entries if entry['case'] == packet['case'])
    evidence_images.validate_inputs([entry])
    unique = {}
    for row in packet['calls']:
        for ref in row.get('image_inputs', []):
            unique.setdefault((ref['path'],ref['sha256']), {'ref':ref, 'calls':[]})['calls'].append(row['request'])
    if not unique: return [], []
    images = []; metadata = []
    for item in unique.values():
        ref = item['ref']
        path=evidence_images.resolve_image_path(evidence_images.image_relative_paths(entry,ref['path']),ref['sha256'])
        raw = evidence_images.image_bytes(str(path),ref['sha256'])
        original_sha = hashlib.sha256(raw).hexdigest()
        if ref.get('transmitted_png_sha256') and original_sha!=ref['transmitted_png_sha256']:
            raise ValueError('Candidate image rasterization SHA changed: '+ref['path'])
        variants = {}
        for row in packet['calls']:
            if row['request'] not in item['calls']: continue
            matches = [binding for binding in delivery_index.get(str(row['request']), [])
                       if binding['original_png_sha256'] == original_sha]
            for binding in matches:
                variants[binding['transmitted_png_sha256']] = binding
        if not variants: variants[original_sha] = None
        for sha, binding in variants.items():
            if binding is None:
                data = raw
            else:
                with Image.open(io.BytesIO(raw)) as source:
                    resized = adaptation.resize_canvas_strips(source, tuple(binding['transmitted_size']))
                with resized:
                    output = io.BytesIO()
                    # v2/v3 used Pillow's default PNG encoding; v4+ records the
                    # byte budget and uses optimized level-9 encoding. Rebuild
                    # the exact historical bytes, not merely the same pixels.
                    options={'optimize':True,'compress_level':9} if 'original_base64_bytes' in binding else {}
                    resized.save(output,format='PNG',**options)
                    data = output.getvalue()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError('Cannot reconstruct recorded candidate image SHA: ' + ref['path'])
            label = compact({'evidence_image':ref,'candidate_request_numbers':item['calls'],
                'original_png_sha256':original_sha,'transmitted_png_sha256':sha,
                'transmission':binding or 'original_png_bytes'})
            if protocol == 'messages':
                parts, tiles = adaptation.message_image_parts(data, len(images))
                images.append({'type':'text','text':label}); images.extend(parts)
            else:
                images.extend([{'type':'input_text','text':label}, {'type':'input_image',
                    'image_url':'data:image/png;base64,'+base64.b64encode(data).decode()}])
            metadata.append({'path':ref['path'],'transmitted_png_sha256':sha,'calls':item['calls']})
    return images, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--delivery',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--resource-root',type=Path)
    parser.add_argument('--base-url',default='https://mp.z01.normandyfunc.com/v1')
    args = parser.parse_args()
    key = os.environ['REDACT_API_KEY']
    packet = json.loads(args.packet.read_text()); template = json.loads(args.template.read_text())
    case_directory = args.output / 'raw-responses' / packet['case']
    destination = args.output / 'judgments' / (packet['case']+'.json')
    result_path = args.output / 'case-status' / (packet['case']+'.json')
    if destination.exists():
        judgment = json.loads(destination.read_text());metrics=judge_protocol.validate(judgment,packet)
        previous=json.loads(result_path.read_text()) if result_path.exists() else {}
        previous.update(status='complete',case=packet['case'],reused=True,metrics=metrics,
                        needs_primary_review=judgment['needs_primary_review'])
        write(result_path,previous)
        return
    protocol = 'messages' if args.model.startswith('claude-') else 'responses'
    text = judge_protocol.prompt(packet,template)
    original_chars = len(compact(packet))
    resource_root=args.resource_root or args.output.parent.parent
    resource_root.mkdir(parents=True,exist_ok=True)
    # Serialize only memory-heavy local image work; remote text judging overlaps.
    with (resource_root/'.judge-heavy.lock').open('a+') as image_lock:
        fcntl.flock(image_lock,fcntl.LOCK_EX)
        if any(row.get('image_inputs') for row in packet['calls']):
            from run_judge import aggregate_rss
            while aggregate_rss()+402653184>1468006400:time.sleep(5)
        images, image_metadata = image_parts(packet,json.loads(args.delivery.read_text()),protocol)
    # New recovery attempts retain all prior raw responses instead of overwriting.
    if case_directory.exists():
        import uuid
        case_directory=case_directory/('recovery-'+uuid.uuid4().hex[:12])
    messages = [{'type':'text' if protocol=='messages' else 'input_text','text':text}] + images
    headers = {'Authorization':'Bearer '+key,'Content-Type':'application/json'}
    if protocol=='messages': headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    feedback = None
    for attempt in range(1,4):
        content = messages
        if feedback is not None:
            content = messages + [{'type':'text' if protocol=='messages' else 'input_text','text':feedback}]
        if protocol=='messages':
            body={'model':args.model,'system':judge_protocol.SYSTEM,'messages':[{'role':'user','content':content}],
                  'max_tokens':16384,'temperature':1.0}
        else:
            body={'model':args.model,'input':[{'role':'system','content':[{'type':'input_text','text':judge_protocol.SYSTEM}]},
                  {'role':'user','content':content}],'max_output_tokens':16384,'store':False}
        payload = compact(body).encode(); request_sha = hashlib.sha256(payload).hexdigest()
        request = urllib.request.Request(args.base_url.rstrip('/')+'/'+protocol,data=payload,headers=headers)
        started = time.monotonic()
        write(result_path,{'status':'judging','case':packet['case'],'attempt':attempt,'started_at':time.time(),
            'original_packet_characters':original_chars,'judge_text_characters':len(text),'images':len(image_metadata)})
        saved = None
        try:
            with urllib.request.urlopen(request,timeout=300) as response: raw=json.load(response)
            # No credentials or private reasoning are used as judgment evidence.
            from provider_bridge import normalize
            normalized = normalize(raw,protocol); visible=normalized['choices'][0]['message']['content']
            saved={'attempt':attempt,'request_sha256':request_sha,'request_bytes':len(payload),
                'model':args.model,'reported_model':raw.get('model'),'response_id':raw.get('id'),
                'usage':raw.get('usage'),'finish_reason':normalized['choices'][0]['finish_reason'],
                'text':visible.replace(key,'[REDACTED]'),'seconds':round(time.monotonic()-started,3),
                'evidence_images':image_metadata,'packet_sha256':hashlib.sha256(args.packet.read_bytes()).hexdigest()}
            write(case_directory / (f'attempt-{attempt:02d}.json'),saved)
            judgment=judge_protocol.parse(saved['text'])
            metrics=judge_protocol.validate(judgment,packet)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as exc:
            detail = (exc.read(2000).decode(errors='replace') if isinstance(exc,urllib.error.HTTPError) else str(exc)).replace(key,'[REDACTED]')
            write(case_directory / (f'http-error-{attempt:02d}.json'),{'attempt':attempt,'error':detail,
                'status':getattr(exc,'code',None),'seconds':round(time.monotonic()-started,3),'request_sha256':request_sha})
            if attempt==3: raise RuntimeError('Judge API failed: '+detail) from None
            time.sleep(min(60,10*2**attempt));continue
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            detail=str(exc).replace(key,'[REDACTED]')
            write(case_directory / (f'validation-{attempt:02d}.json'),{'error':detail})
            if attempt==3:
                write(result_path,{'status':'needs_review','case':packet['case'],'error':detail,'attempts':attempt})
                return
            feedback='Your previous response failed validation: '+detail+'. Re-evaluate against all original evidence, correct the schema/evidence paths, and return the complete judgment JSON. Do not invent evidence or deadlines.'
            if saved is not None: feedback += ' Previous JSON:\n'+saved['text']
            continue
        write(destination,judgment)
        write(result_path,{'status':'complete','case':packet['case'],'attempts':attempt,
            'needs_primary_review':judgment['needs_primary_review'],'metrics':metrics,'reported_model':raw.get('model'),
            'usage':raw.get('usage'),'original_packet_characters':original_chars,'judge_text_characters':len(text),
            'images':image_metadata,'seconds':saved['seconds']})
        print(compact({'case':packet['case'],'status':'complete','needs_primary_review':bool(judgment['needs_primary_review'])}),flush=True)
        return


if __name__=='__main__':
    try: main()
    except Exception as exc:
        key=os.environ.get('REDACT_API_KEY','')
        message=str(exc).replace(key,'[REDACTED]') if key else str(exc)
        print(type(exc).__name__+': '+message,file=sys.stderr)
        raise SystemExit(2)
