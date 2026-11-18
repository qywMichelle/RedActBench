"""Bilingual batch018 authoring with distinct synthetic host histories."""
from helpers import *
HOSTS={
 't1-01':('Lena','I edit the reading club newsletter. I like short openings and a clear next step.|我编读书会社讯。开头短一点，接下来做什么说清楚。','The kettle is on. Bring the book you actually finished; half-finished counts too.|水烧上啦。带真正读过的那本，读一半也算。','The room vote is settled: upstairs on Tuesday. I changed the calendar as well.|房间票定了：周二楼上，日历也改过了。'),
 't1-02':('Tess','I organize skills sessions for volunteers. I usually write in full but short sentences.|我给志愿者组织技能课，习惯完整但简短地说事。','The notes are up. Skip to page three if you only need the exercise.|笔记放好了。只想看练习的话直接翻第三页。','Six people asked for a later start. That is a useful signal; I will ask about room availability next.|六个人希望晚点开始。这个信息很有用，我接下来问场地时间。'),
 't2-01':('Noah','I help former students meet people in creative careers. I keep introductions warm and brief.|我帮毕业生认识创意行业的前辈。引荐尽量亲切、简短。','I think you two would get on. Shall I ask her if she is up for a chat first?|感觉你们聊得来。我先问问她愿不愿意聊？','No rush on the portfolio. The two questions give us enough to start.|作品集不用急。有这两个问题，先聊起来就够了。'),
 't3-01':('Rory','I coordinate the market volunteers. During a shift I lead with the place and time.|我协调市集志愿者。值班时先说地点和时间。','North gate at four, please. The red trolley can wait until after the handover.|麻烦四点到北门。红推车等交班后再管。','Thanks, everyone. We got all six tables indoors before the rain found them.|谢谢大家。雨还没找过来，六张桌子都搬进去了。'),
 't4-01':('June','I post community photo recaps. I am chatty about the event, quieter about personal requests.|我发社区活动照片回顾。活动可以聊热闹些，个人请求私下简短处理。','The confetti is still turning up in my bag. Here are the photos from Saturday.|彩纸还在我包里冒出来。周六的照片来啦。','Got it. I took that shot out of the public post and left the rest as they were.|收到。那张已从公开帖里拿掉，其他照片保留。'),
 't5-01':('Dev','I look after the community library equipment. I use plain names and times rather than booking jargon.|我管社区图书馆器材。用大家看得懂的设备名和时间，不爱写预约术语。','The small speaker is back on the middle shelf. Its charger is in the blue pouch.|小音箱回中层架子了，充电器在蓝袋里。','You can keep the screen through the last slide. I will arrange the next pickup around that.|最后一页放完再还幕布就行。我按这个时间排下一次取件。'),
 't5-03':('Iris','I produce a small theatre night. My public posts have a little warmth; invoices get straight facts.|我做小剧场演出。公开帖留点温度，账单直接说事实。','One more rehearsal and then we let you in on the secret. Friday, seven sharp.|再排一次，就带你们进故事里。周五七点，准时开场。','I put the delivery fee on the wrong invoice. It is corrected now; the sound booking stays as agreed.|我把送货费记错账单了。现在改好了，音响预约照旧。')}
def begin(sid,title,task,brief,deadline=100):
 from task_language_overrides import task_for
 task=task_for(sid,task)
 name,profile,h1,h2=HOSTS.get(sid,(sid.replace('-',' ').title(),'I organize this small project and write directly to the people involved.|我组织这个小项目，习惯直接跟相关的人说清楚。','Thanks for making time. I have put the next date in the calendar.|谢谢大家腾时间，下次日期已放进日历。','That was my mistake. I changed the details and let the people affected know.|是我记错了，内容已改，也通知了受影响的人。'))
 profile_data={'text':T(profile),'display_name':name,'user_id':'creator','role':'fictional host'}
 history=[('An ordinary public update|一次日常公开更新',h1),('An earlier correction or private arrangement|此前一次更正或私下安排',h2)]
 try:
  from profile_overrides import profile_for
  profile_data,history=profile_for(sid,profile_data,history)
 except ImportError:pass
 return Case(sid,title,task,brief,profile_data,history,deadline)
def goal(x,label,text,ids,alt=None):return x.goal(label,text,ids,alternative=alt)
def plans(x,actions,bad1,g1,bad2,g2,alternative=None):
 return install_plans(x,actions,bad1,g1,bad2,g2,alternative=alternative or actions)
def waiting():return {'action':'WAIT_FOR_IDS','ids':[]}
def bind_noop(x):return x
