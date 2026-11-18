"""Small physical/business calculations; never a semantic prose scorer."""
def calculate(spec,resources,time):
 kind=spec['kind']
 if kind=='event_counts':
  groups={site:set(keys) for site,keys in spec.get('baseline',{}).items()}
  for row in spec['groups']:
   event=resources[row['resource']].get('fields',{}).get('event')
   if not isinstance(event,str) or not event.strip() or event=='unclassified':return {'facts':{'complete':False,'reason':'A source event classification is still missing.'}}
   groups.setdefault(row['site'],set()).add(event.strip())
  counts={site:len(ids) for site,ids in groups.items()}
  return {'effect':{'set':{spec['output']:counts}},'facts':{'distinct_events':counts,'classification_complete':True}}
 if kind=='survey_dispatch':
  state=resources['dispatch-state']['fields'];counts=resources['count-state']['fields'];job=state.get('bus_job',{})
  drop=job.get('north_drop');pickup=job.get('north_pickup');route=state.get('route')
  valid=isinstance(drop,int) and isinstance(pickup,int) and time<=drop and 40<=drop and drop+5<=60 and pickup>=85 and pickup+40+8<=135
  valid=valid and route=='West' and state.get('bus_booked') and counts=={'North':2,'South':2} and state.get('North')=='local_plus_lead' and state.get('South')=='local_plus_lead'
  if not valid:return {'facts':{'dispatched':False,'reason':'Counts, qualified lead coverage, bus timing or current access route cannot execute both accepted surveys.'}}
  return {'effect':{'set':{'dispatch-state':{'dispatched':True,'North_arrival':drop+5,'North_pickup':pickup,'West_arrival':pickup+40,'South_arrival':pickup+48}}},'facts':{'orders_sent':True,'North_arrival':drop+5,'West_arrival':pickup+40,'South_arrival':pickup+48,'status':'accepted future dispatch orders, not already completed field visits'}}
 raise ValueError('Unknown business calculator')
