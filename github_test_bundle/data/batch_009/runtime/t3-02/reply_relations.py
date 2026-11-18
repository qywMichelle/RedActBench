"""Bounded current-speech relationships. This is not unrestricted NLP/scoring.

The controller declares ordinary object/time relationships, never candidate route
labels. Actual prose must deliver those relationships; transported cards cannot
supply missing or contradictory speech acts. Ambiguity means nonbinding feedback.
"""
import re

def active_material(text):
    """Keep current delivered material; drop quotes introduced as past/reporting."""
    text=text.replace('’',"'")
    pattern=r'[“\"].*?[”\"]|(?<!\w)\x27[^\x27]*\x27(?!\w)'
    def replace(m):
        prefix=text[max(0,m.start()-100):m.start()]
        intro=re.split(r'[.!?;\n]',prefix)[-1]
        if re.search(r'\b(?:use|follow|here are|current|actual)\b.{0,50}\b(?:instructions?|directions?|method|steps)\b\s*:\s*$',intro,re.I):
            return m.group()[1:-1]
        return ' '
    return re.sub(pattern,replace,text,flags=re.S)

def clauses(text):return [p.strip().lower() for p in re.split(r'(?<=[.!?])\s+|[;\n]+',active_material(text)) if p.strip()]

def historical(part):
    return bool(re.match(r'\s*(?:the |an? )?(?:old|earlier|previous|historical|draft)\b',part) or re.match(r'\s*(?:you|they) (?:said|wrote)\b',part))

def _requirement_atoms(text):
    # Small lexical normalizations preserve the asserted predicate/property.
    text=re.sub(r'\b(?:no[- ]charge|no[- ]cost) cancellation\b','free cancellation',text)
    text=re.sub(r'\bcancellation (?:at |for )?no charge\b','free cancellation',text)
    forms={'confirmed':'confirm','confirms':'confirm','confirming':'confirm','verified':'verify','verifies':'verify','guaranteed':'guarantee','guarantees':'guarantee','approved':'approve','approves':'approve','returned':'return','returns':'return','checked':'check','checks':'check','paid':'pay','sent':'send','received':'receive','readiness':'ready'}
    stop=set('the a an this that its is are was were has have had been be being already actually currently now only after before to of for on in at with and would will shall can could does do then provided'.split())
    return [forms.get(w,w) for w in re.findall(r"[a-z0-9_-]+",text.lower()) if w not in stop]


def _one_requirement_open(condition,before,prior):
    if re.match(r'you (?:accept|want|would like|choose)\b',condition):return False
    if re.match(r'you (?:(?:can|will) )?(?:attend|collect|pick up|return|arrive|pay)\b',condition):return False
    required=_requirement_atoms(condition)
    desired_negative=any(w in required for w in ['not','no','never'])
    required=[w for w in required if w not in ['not','no','never']]
    if len(required)<2:return True
    subject,properties=required[0],set(required[1:])
    context=set(re.findall(r'\b[a-z]+[0-9]+\b',before))
    assertions=re.split(r'[;.!?,]',prior+'; '+before)
    for assertion in reversed(assertions):
        assertion=assertion.strip()
        if historical(assertion) or re.search(r'\b(?:if|whether|pending|unverified|unconfirmed|unknown|awaiting|might|would|will|offer|proposal)\b',assertion):continue
        named=set(re.findall(r'\b[a-z]+[0-9]+\b',assertion))
        if context and named and not context.intersection(named):continue
        words=_requirement_atoms(assertion)
        if subject not in words:continue
        tail=set(words[words.index(subject)+1:])
        # Concrete checked/available camera evidence can express readiness; a
        # mere booking confirmation cannot silently supply that other property.
        if subject in ['camera','kit'] and 'check' in tail and ('available' in tail or 'return' in tail):tail.add('ready')
        if properties<=tail:
            negative=bool(re.search(r"\b(?:not|no|never|cannot|can't|hasn't|haven't|didn't|no longer)\b",assertion))
            return negative!=desired_negative
    return True


def unresolved_condition(part,prior=''):
    """Check every explicit condition; courtesy does not waive another predicate."""
    markers=list(re.finditer(r'\b(?:only if|subject to|provided that|only after|if)\b',part))
    for i,m in enumerate(markers):
        end=markers[i+1].start() if i+1<len(markers) else len(part)
        condition=re.split(r',|\bthen\b',part[m.end():end])[0].strip()
        requirements=re.split(r'\band\s+(?=(?:the\s+)?[a-z][a-z0-9_-]*\s+(?:is|are|has|have|was|were|guarantees|confirms|supports)\b)',condition)
        for requirement in requirements:
            if _one_requirement_open(requirement,part[:m.start()],prior):return True
    return False

def collection_directions(text,terms,contract):
    """Finite affirmative pickup/return relationship with current qualifier scope."""
    parts=clauses(text)
    for i,part in enumerate(parts):
        if historical(part):continue
        cue=re.search(r'(?:^|[:,]\s*(?:and\s+)?)(?:please\s+)?(?:(?:now|actually)\s+)?(?:collect|pick\s+(?:(?:both(?:\s+(?:pieces|items|components))?|the\s+(?:kit|set))\s+)?up)\b|\byou (?:can|may|should|will|must)\s+(?:now\s+)?(?:collect|pick\s+up)\b',part)
        if not cue:continue
        prefix=part[:cue.start()]
        if re.search(r'\b(?:draft|quote|said|wrote|received)\b',prefix) and not re.search(r'\b(?:use|follow|current|actual)\b.{0,50}\b(?:instructions?|directions?)\b',prefix):continue
        if re.search(r"\b(?:do not|don't|never|must not|mustn't|cannot|can't|should not|shouldn't|whether|hypothetical)\b",prefix):continue
        if unresolved_condition(part,'; '.join(p for p in parts[:i] if not historical(p))):continue
        # Adjacent explicit qualification of the current plan remains operative.
        suffix=parts[i+1:i+3]
        qualified=False
        for following in suffix:
            if historical(following):continue
            refers=re.search(r'\b(?:this|that|these|the current)\s+(?:offer|proposal|arrangement|plan|instructions?|directions?|permission|approval)\b',following)
            if refers and re.search(r'\b(?:conditional|hypothetical|pending|unverified|awaiting|not yet|not final)\b',following):qualified=True
            if re.search(r'\b(?:no|not|withhold\w*)\b[^.!?;]{0,35}\b(?:instructions?|directions?|permission|approval)\b[^.!?;]{0,30}\b(?:issued|given|sent|approved|provided)\b',following):qualified=True
        if qualified:continue
        segment=part[cue.start():]
        ret=re.search(r'\breturn(?:\b|(?=\d))',segment)
        if not ret and i+1<len(parts) and re.match(r'^(?:please )?return(?:\b|(?=\d))',parts[i+1]):
            segment+='; '+parts[i+1];ret=re.search(r'\breturn(?:\b|(?=\d))',segment)
        if not ret:continue
        pick=segment[:ret.start()];back=segment[ret.end():]
        names=contract.get('objects',[])
        if names:
            group=r'\b'+re.escape(names[0])+r'\s*(?:\+|and|with|plus)\s*(?:(?:module|adapter|body)\s*)?'+re.escape(names[1])+r'\b' if len(names)==2 else r'\b'+re.escape(names[0])+r'\b'
            if not re.search(group,pick,re.I):
                antecedent=parts[i-1] if i else ''
                if not (re.search(r'\b(?:both|this set|the set|the kit)\b',pick) and not historical(antecedent) and re.search(group,antecedent,re.I)):continue
        def times(value):
            return [m.group() for m in re.finditer(r'(?<!\d)\d{1,2}:\d{2}(?!\d)',value) if not re.search(r'\b(?:not|rather than|instead of)\s*$',value[max(0,m.start()-25):m.start()])]
        pick_times=times(pick);back_times=times(back)
        if not pick_times and re.match(r'^at\b',prefix):pick_times=times(prefix)[-1:]
        expected_pick=re.findall(r'(?<!\d)\d{1,2}:\d{2}(?!\d)',str(terms.get(contract.get('pickup_field','start'),'')))
        expected_back=re.findall(r'(?<!\d)\d{1,2}:\d{2}(?!\d)',str(terms.get(contract.get('return_field','return'),'')))
        if not pick_times or not back_times or not expected_pick or not expected_back:continue
        if any(t not in expected_pick for t in pick_times) or any(t not in expected_back for t in back_times):continue
        return True
    return False
