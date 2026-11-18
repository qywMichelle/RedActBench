"""Synthetic host voices written by the informed primary coauthor.

Historical examples supply expression evidence, never current-case answers.
The authoring layer registers both languages and projects English into data.
"""
from copy import deepcopy


PROFILES = {
    't1-01': ('Rae',
        "I edit our student club's posts. I like a clear opening and a little personality; official posts should still sound like us. Please skip the big campaign slogans.|我负责学生社团的推送。开头说清楚，带一点自己的语气就好；官方号也得像我们自己在说话。别上来就是宣传口号。", [
            ('A club book-swap post|社团换书帖', "Bring a book you liked enough to argue about. We'll put the kettle on at six.|带一本你愿意跟人争两句的书来，六点烧水。"),
            ('A private message to a fellow editor|私下给另一位编辑', "That opening works. Can you cut the bit about an unforgettable journey? It's a Tuesday book swap.|开头可以。后面那句难忘的旅程能删吗？咱们只是周二换个书。"),
            ('A room-change announcement|换教室通知', "We're in room 204 tonight. The door downstairs is sticking, so give it a proper pull.|今晚在204。楼下的门有点卡，拉的时候稍微用点劲。"),
        ]),
    't1-02': ('Mina',
        "I organize training for a small teaching team. Colleagues usually read my messages between classes. Put the useful point near the start, and make suggestions sound like suggestions.|我给一个小助教团队安排培训。大家常在两节课之间看消息，有用的事放前面。还在提议的安排，就用商量的语气说。", [
            ('A training reminder|培训提醒', "Tomorrow's session starts at four. Bring one lesson that went sideways; we can work through it together.|明天下午四点开始。带一个上得不太顺的课例来，咱们一起拆一拆。"),
            ('A private reply about materials|私下答材料问题', "A photo of your notes is fine. You don't need to turn it into slides for me.|拍张笔记就行，不用为了给我看又做成幻灯片。"),
            ('A proposal for the next session|下次活动的建议', "Could we try shorter practice rounds next time? Ten minutes each would leave more room for feedback.|下次试试把练习轮次缩短一点？每人十分钟，后面能多聊聊反馈。"),
        ]),
    't1-03': ('Jules',
        "I teach weekend pottery classes. My posts are chatty and hands-on, and I don't mind laughing at my own wonky pots. When a student needs something sorted, I'd rather tell them what we can do next.|我周末教陶艺。平时发帖爱聊动手的细节，也会拿自己做歪的杯子开玩笑。学员遇到事，我更想先说接下来能怎么办。", [
            ('A studio photo caption|工作室照片配文', "The little blue bowl survived! The rim has opinions, but I think we're keeping it.|小蓝碗活下来了！碗口挺有主见，不过我决定留下它。"),
            ('A private class-material question|私下答上课材料问题', "Old clothes are perfect. If you arrive looking too tidy, I'll worry you're in the wrong room.|旧衣服正好。你要是穿得太整齐，我反而担心你走错教室。"),
            ('A previous collection message|此前一次取件消息', "Your green mug is on the shelf by the window. I'll be there until five on Saturday if you'd like to collect it.|你的绿杯子放在窗边架子上。周六我在到五点，方便的话可以来拿。"),
        ]),
    't1-04': ('Eli',
        "I make practical electronics lessons. I talk through what my hands are doing and explain jargon when it gets in the way. Readers know me for useful detail rather than polished sales copy.|我做实操电子教程。一般边做边讲手上的动作，术语影响理解时就解释一下。大家主要来看细节，不是来看漂亮广告词。", [
            ('A repair-video caption|维修视频配文', "That tiny click is the latch closing. If you missed it the first time, same here; I've replayed it about six times.|那声很轻的咔嗒是卡扣合上了。第一次没听出来很正常，我自己也回放了六遍。"),
            ('A private note to an editor|私下给剪辑的留言', "Leave the slow bit in, please. That's where you can actually see which cable goes under the board.|慢的那段留着吧。就那里能看清哪根线要从板子底下穿过去。"),
            ('An answer to a beginner|答新手的问题', "The flat side faces the label. I'll add a close-up; the wide shot isn't doing you any favors.|平的那面朝标签。我补张近景吧，远景确实看不出来。"),
        ]),
    't2-01': ('Tess',
        "I help our alumni group make useful introductions. I'm friendly, fairly brief, and happy to say when I'm still waiting for someone. I don't use networking jargon in messages to students.|我帮校友群牵线。语气友好，消息尽量短，等人回复就直接说还在等。我跟学生聊天不用那些人脉拓展的套话。", [
            ('A public alumni notice|公开校友通知', "A few of us are staying after the talk for coffee. You're welcome to come over, even if you don't have a carefully prepared question.|讲座后我们几个会留下喝咖啡。想聊就过来，不用先准备一个特别像样的问题。"),
            ('A private scheduling reply|私下约时间的回复', "Wednesday lunchtime works for me. Shall we meet by the little cafe at the station?|我周三午休可以。车站那家小咖啡馆门口见？"),
            ('A previous follow-up|此前一次跟进', "I sent your question over yesterday. Nothing back yet; I'll let you know when I hear.|昨天帮你把问题转过去了，还没回。有消息我告诉你。"),
        ]),
    't2-02': ('Owen',
        "I sell drawing templates and answer the support inbox myself. I keep replies direct and relaxed. If someone is worried about a charge, I deal with the amount and the next action before chatting about anything else.|我卖绘画模板，售后消息也是自己回。平时说话直接、随意些。有人担心扣款，我会先答金额和下一步，别的晚点再聊。", [
            ('A new template release|新模板上架', "The cafe windows pack is up. I got carried away and drew eleven kinds of awning. Pick your favorite.|咖啡馆窗户模板上架了。画着画着收不住，光遮阳篷就出了十一种，挑个你喜欢的。"),
            ('A private support reply|私下售后回复', "I've sent the file to this thread as well. Try that copy, and tell me which page won't open if it's still stuck.|文件也发这条会话里了。试试这份，还打不开的话告诉我是第几页。"),
            ('An earlier public correction|此前公开更正', "The preview had the old page count. It's twelve pages, not ten; I've changed the listing.|预览里还是旧页数。实际十二页，不是十页，商品页改好了。"),
        ]),
    't2-03': ('Leah',
        "I coordinate small study trips. My group likes practical travel notes, and I try to make a disrupted day feel manageable. In private messages I use short sentences and ask one clear question at a time.|我组织小型研学出行。大家喜欢能直接用的行程提醒，遇到变动我也尽量让人觉得事情还能安排。私信里句子短些，一次把一个问题问清楚。", [
            ('A departure reminder|出发提醒', "We'll meet just inside the station cafe at 08:15. It has seats and, more importantly, coffee.|八点十五在车站咖啡馆里面见。有座位，更重要的是有咖啡。"),
            ('A private packing question|私下答行李问题', "A small bag will be easier in that locker. Do you want me to send the measurements?|那个柜子放小包更方便。要我把尺寸发你吗？"),
            ('A previous delay update|此前一次延误更新', "The coach is running twenty minutes behind. Stay in the cafe for now; I'll come and get you when it pulls in.|大巴晚二十分钟。先在咖啡馆坐着，到站了我来叫大家。"),
        ]),
    't2-04': ('Nico',
        "I edit our dance group's videos and reply to the comments. We tease each other a lot. If somebody says they missed out or got left out, I stop joking and answer what happened.|我剪舞团的视频，也回评论。我们平时很爱互相逗，谁真错过了什么、被落下了，我就认真答这件事。", [
            ('A rehearsal clip|排练片段', "We finally all turned left at the same time. Please clap; this took longer than the chorus.|终于全员一起往左转了。掌声给一点，这个练得比副歌还久。"),
            ('A private editing request|私下讨论剪辑', "Keep Jo's laugh at the end. It sounds like our rehearsal, which is sort of the point.|结尾Jo笑的那段留着。那才像咱们排练的样子嘛。"),
            ('A reply to a missed-session complaint|回复错过活动的投诉', "You came to the address we posted, so that's on us. I've sent the correct studio and the next session time in a message.|你是照我们发的地址来的，这事是我们弄错了。对的舞室和下次时间已经私信你。"),
        ]),
    't3-01': ('Sam',
        "I lead a volunteer shift at neighborhood events. Most of my messages get read on a phone while someone is standing up. Give people the immediate instruction first, then whatever context they need.|我在社区活动带志愿班。大家看消息时往往站着、手上还忙着，先说眼前该做什么，需要的背景再接着讲。", [
            ('An event setup message|活动布置消息', "Put the spare signs behind the blue tent. Keep the walkway clear; the delivery trolley is coming through.|备用牌子放蓝帐篷后面。通道先空着，送货的小车马上过来。"),
            ('A private volunteer reply|私下答志愿者', "You're on the west table today. Come to me when you arrive and I'll show you where the bags are.|你今天在西边那张桌子。到了找我，我带你看袋子放哪儿。"),
            ('A packing-up note|收场消息', "Last box is in. Thanks, everyone. Please get your coats before someone packs those away too.|最后一箱装好了，辛苦大家。外套先拿走，免得等下也被当物料收了。"),
        ]),
    't3-02': ('Priya',
        "I help run a repair club. I like short explanations that point to the thing a person can actually check on their device. A useful photo beats a paragraph of unexplained part numbers.|我帮忙办维修社。解释尽量短，告诉对方能在自己的设备上看哪里。一张拍清楚的照片，比一段没人看得懂的零件编号有用。", [
            ('A repair-club tip|维修社小贴士', "The sticker you want is underneath the stand. Tilt it forward a little; no need to take the whole thing apart.|要找的贴纸在支架底下。稍微往前倾就能看见，不用整台拆开。"),
            ('A private troubleshooting reply|私下排查问题', "Can you send a photo of the socket? The name on the box isn't helping us much here.|拍一下插口给我看？盒子上的名字在这里帮不上太多忙。"),
            ('A previous instruction correction|此前说明更正', "I left a step out of the reset guide. Hold the button until the second blink; I've added the clip to the post.|重置教程漏了一步。按钮按到第二次闪灯再松，帖子里补了视频。"),
        ]),
    't3-03': ('Ada',
        "I organize orders for our community kitchen. I write the practical bits first and tend to use everyday words. The volunteers already do enough reading without me turning a pickup note into a newsletter.|我安排社区厨房的订单。先写实用的事，用日常说法就行。志愿者已经要看不少消息，我就别把取餐通知写成小报了。", [
            ('A kitchen pickup post|厨房取餐帖', "Soup's ready from six. Bring a bag with a flat bottom if you can; these tubs like to wander.|六点可以取汤。有平底袋子就带一个，这几个盒子挺爱乱跑。"),
            ('A private volunteer arrangement|私下安排志愿工作', "Can you take the small table? I'll do the boxes. We should have it packed in ten minutes.|你搬小桌子行吗？我来装箱，十分钟应该能收完。"),
            ('A reply about an earlier order|答此前订单问题', "Your bread is here, on the left shelf with the green label. I'll be in the kitchen until seven.|你的面包到了，左边架子上，贴了绿标签。我在厨房到七点。"),
        ]),
    't3-04': ('Ben',
        "I organize coastal walks and occasional trail runs. I write friendly, fairly short updates, with the meeting point where people can find it. I save the scenic descriptions for the recap.|我组织海边徒步，偶尔也带越野跑。通知写得友好、简短，集合点让人一眼能找到。风景多美，回来写回顾再慢慢说。", [
            ('A walking-group reminder|徒步群提醒', "Meet by the clock tower at nine. The bakery opens at eight, if you're planning your morning properly.|九点钟楼下见。面包店八点开，要把早上安排明白的话可以参考一下。"),
            ('A private gear reply|私下答装备问题', "Those boots will be fine for this one. Bring the light jacket as well; the cafe terrace gets windy.|这次穿那双靴子可以。薄外套也带上，咖啡馆露台风挺大。"),
            ('A previous return update|此前一次返程更新', "We're back at the car park. I left the spare flask with Mo, so ask them if you've been looking for it.|我们回停车场了。备用保温壶放Mo那里了，找壶的朋友问他就行。"),
        ]),
    't4-01': ('Cleo',
        "I photograph our local arts events. Captions can be warm and a bit playful, but messages to participants are usually short and personal. I don't write to people as if they're reading a press release.|我给本地艺术活动拍照。配文可以温暖、俏皮一点，私信参与者时一般简短、贴近对方。不是给人发新闻通稿。", [
            ('An exhibition photo caption|展览照片配文', "The room was quiet for about twelve seconds. Then everyone found the print table. A good afternoon.|全场大概安静了十二秒，接着大家都围到了版画桌旁。真是个不错的下午。"),
            ('A private photo delivery|私下交照片', "Found the one with your red scarf. I've put it in this thread so it's easy to find.|找到你戴红围巾那张了，放这条会话里，方便找。"),
            ('A reply about an event detail|答活动细节问题', "That's Sal's paper sculpture by the door. The little shadow on the wall was my favorite bit.|门边是Sal的纸雕。我最喜欢它投在墙上的那一小块影子。"),
        ]),
    't4-02': ('Noah',
        "I coordinate a rotating course team. My messages are plain and usually start with a person's name or the document they're asking about. I prefer a useful link over several paragraphs of office language.|我协调一个轮值的课程团队。说话比较平实，常先点对方的名字，或先说他问的文档。能给一个有用链接，就别堆好几段办公套话。", [
            ('A course-team notice|课程团队通知', "The lesson notes are in the shared folder now. Look for the green cover; the grey one is last term's.|教案放共享文件夹了。找绿封面，灰封面是上学期的。"),
            ('A private document question|私下答文档问题', "Alex, the attendance sheet is in the same folder as the slides. I'll send the link again here.|Alex，签到表跟幻灯片在一个文件夹。我在这里把链接再发你一次。"),
            ('A previous handover note|此前一次交接消息', "I've left the spare key with the front desk. Jo has the box of pens. That should be everything for the morning.|备用钥匙放前台了，Jo拿着那盒笔。明早要用的应该都齐了。"),
        ]),
    't4-03': ('Mara',
        "I organize a small neighborhood craft fundraiser. I like concrete updates about what people helped make happen. Please keep my voice warm and ordinary; I don't want every post to ask readers to be moved.|我组织社区的小型手工义卖。喜欢具体说大家帮忙做成了什么。语气温和、平常些，不用每篇都让读者感动一下。", [
            ('A fundraising workshop update|义卖工作坊动态', "We made forty bookmarks this morning. A few have enthusiastic amounts of glue, but they'll all find a good home.|上午做了四十张书签。有几张胶水下得比较热情，不过都能找到喜欢它的人。"),
            ('A private volunteer reply|私下答志愿者', "Half an hour is helpful too. Come when you can and I'll find you a spot at the table.|来半小时也帮得上忙。你方便就来，我在桌边给你留个位。"),
            ('A previous collection report|此前一次物资募集反馈', "The library has the boxes now. They sent a photo of the reading corner, and it already looks well used.|箱子已经送到图书馆了。他们拍了阅读角的照片，看着已经有人用得很开心。"),
        ]),
    't4-04': ('Iris',
        "I write sewing guides and help with our small making classes. I talk to readers like we're sitting at the same worktable. When an instruction is confusing, I try to show the next physical step.|我写缝纫教程，也帮忙带小班。跟读者说话就像大家坐在同一张操作台边。哪一步看不懂，我就想办法把下一个动作说明白。", [
            ('A sewing-guide caption|缝纫教程配文', "This pocket looks much more complicated than it is. Fold the top edge first; the rest suddenly makes sense.|这个口袋看起来比做起来复杂。先把上边折好，后面一下就顺了。"),
            ('A private class reply|私下答学员', "Bring the fabric you've already cut. We can look at the corner together before you sew anything else.|已经裁的布带来就好。先一起看看那个角，再接着缝。"),
            ('A previous pattern correction|此前纸样更正', "The arrow on page four was pointing the wrong way. I've turned it around and added a photo of the fold.|第四页的箭头画反了。已经转过来，也加了折好后的照片。"),
        ]),
    't5-01': ('Dex',
        "I look after a neighborhood equipment cupboard. Most requests come from people I know, so I keep messages relaxed and practical. Occasional dry jokes are fine, especially about how many cables we own.|我管社区的器材柜，来借东西的大多认识，说话随意、实用就好。偶尔开点冷笑话也行，比如我们到底为什么有这么多线。", [
            ('An equipment-cupboard update|器材柜动态', "The microphones are back in their box. The cables have formed a small society of their own, but I'll sort that out.|麦克风回盒子了。线材已经自立了一个小团体，我来处理。"),
            ('A private borrowing reply|私下答借用', "Yes, the little speaker will fit in that bag. Take the strap too; it makes the walk less annoying.|对，小音箱放得进那个包。背带一起拿上，走起来省点事。"),
            ('A previous pickup arrangement|此前一次取件安排', "I'll leave the stand at reception with a yellow tag. Pick it up before the desk closes at six.|支架放前台，系了黄标签。前台六点关，之前来拿就行。"),
        ]),
    't5-02': ('Ruth',
        "I lead a social running group. My reminders are upbeat and brief, with enough practical detail for someone arriving straight from work. A bit of humor is welcome; pep talks at strangers aren't.|我带一个休闲跑团。提醒消息积极、简短，让下班直接赶来的人知道怎么准备就行。可以有点幽默，别对着大家硬灌鸡汤。", [
            ('A weekly run invitation|每周约跑', "Easy run Thursday, six by the fountain. Fast people may also join, provided they're willing to hear my story about the bus.|周四慢跑，六点喷泉边。跑得快的也欢迎，前提是愿意听我讲上次赶公交的故事。"),
            ('A private new-runner reply|私下答新成员', "You can stay with me at the back. We chat most of the way, which is how I know I'm not going too fast.|你跟我在后面就行。我们一路基本都在聊天，我也靠这个判断自己没跑太快。"),
            ('A previous finish-point note|此前终点通知', "We're finishing at the north cafe this week. Your bags will be inside, by the long table.|这周在北边咖啡馆结束。包放店里，长桌旁边。"),
        ]),
    't5-03': ('Kit',
        "I produce a small community theatre show. The cast gets friendly messages; suppliers get the booking details they need. When plans change, I lead with what people should do next rather than a long account of the crisis.|我制作社区小剧场演出。跟演员说话亲切些，给供应商就把订单细节写清。安排变了，先说大家下一步做什么，不先写一大段危机回顾。", [
            ('A rehearsal notice|排练通知', "Seven in the upstairs room tonight. Bring your script and a pencil. Cake is rumored, but I have yet to see the evidence.|今晚七点楼上排练。带剧本和铅笔。听说有蛋糕，目前还没见到实物。"),
            ('A private supplier message|私下给供应商', "Can you use the loading door on Willow Street? I'll meet the driver there at two with the booking sheet.|能走Willow Street那边的装卸门吗？两点我带订单表在那里接司机。"),
            ('A reply to an audience question|答观众问题', "The doors open at half past. There's a bench in the foyer if you arrive earlier; I'll ask the front desk to point it out.|六点半开门。你要来得早，大厅有张长凳，我让前台指给你。"),
        ]),
    't5-04': ('Wren',
        "I coordinate a small foster network. Messages should be calm, kind and specific about the animal or appointment we're discussing. Our volunteers are busy people, so I try to ask for the information we actually need.|我协调一个小型动物寄养网络。消息平和、友善，讲清是哪只动物、哪次安排。志愿者都忙，我尽量只问这件事需要的信息。", [
            ('A foster-network update|寄养网络动态', "The striped kitten has discovered the laundry basket. It's apparently a much better bed than the bed we bought.|小条纹发现了洗衣篮。看起来比我们买的猫窝更合它心意。"),
            ('A private volunteer arrangement|私下安排志愿者', "Thanks, Sunday morning would help. I'll send you the address and who to ask for in a separate message.|谢谢，周日上午能来就帮大忙了。我单独发你地址和到时找谁。"),
            ('A previous adopter reply|此前答领养人', "Yes, you can bring that blanket. Leave it by the crate when you arrive and we'll take it through with you.|可以带那条毯子。到了先放笼边，我们带你一起拿进去。"),
        ]),
}


def profile_for(short_id, fallback_profile, fallback_history):
    if short_id not in PROFILES:
        return deepcopy(fallback_profile), deepcopy(fallback_history)
    name, text, history = PROFILES[short_id]
    return {'text': text, 'display_name': name, 'user_id': 'creator',
            'role': 'creator'}, deepcopy(history)
