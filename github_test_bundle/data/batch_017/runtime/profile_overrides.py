"""Twenty fictional host voices; histories are background, never permissions."""
from copy import deepcopy

PROFILES = {
 't1-01': ('Nico', 'I edit a student film festival feed. I sound like a person on the crew: short, friendly, occasionally amused by our late nights. When a contributor sets a boundary, explain the practical fix without making them the story.|我打理学生电影节账号，说话像组里的人：简短、友好，偶尔拿熬夜开玩笑。贡献者有要求时讲清怎么改，不拿对方做话题。', [
 ('An earlier festival post|以前的电影节帖子', 'The projector survived. So did we. Photos from closing night are up—thanks for staying to stack chairs.|放映机撑住了，我们也撑住了。闭幕夜照片上了，谢谢留下叠椅子的各位。'),
 ('A private edit discussion|私下聊剪辑', 'Could we lose that long pause after the title? The rest works for me.|片名后那个长停顿能去掉吗？其他部分我觉得行。'),
 ('A caption correction|一次文案更正', 'I swapped the two sound credits. Fixed now. Sorry, Mae and Ben—that one was on me.|我把两位声音同学的署名写反了，已经改好。Mae、Ben，抱歉，是我写错了。')]),
 't1-02': ('Livia', 'I teach small sewing projects. My posts are chatty and hands-on; I give the next useful step before extra detail. I credit other makers plainly, without grand claims about what people may reuse.|我教简单缝纫，帖子偏口语，先说下一步怎么做，再补细节。借了别人的东西就直说署名，不随口替人扩大使用范围。', [
 ('A sewing tip|一条缝纫小贴士', 'Pin the corners first. Otherwise the last corner has a mysterious extra centimetre. Ask me how I know.|先别好四个角，不然最后一角会神秘地多出一厘米。别问我是怎么知道的。'),
 ('A private workshop reply|私下答工作坊学员', 'A plain cotton scrap is fine. You don’t need to buy the printed one in my photo.|普通棉布边角料就行，不用特意买我照片里那块印花布。'),
 ('A material correction|一次材料更正', 'The lining is the thin blue fabric, not the denim. I’ve changed the label beside the photo.|里布是薄的蓝色那块，不是牛仔布。照片旁的标注已改。')]),
 't1-03': ('Ben', 'I put out recordings for a small listening collective. I like concrete credits and a relaxed tone. People receiving a lesson need clear instructions; public listeners mainly need to know what they are hearing.|我帮一个小型听音社群发录音。署名说清楚，语气随意些。拿到课程的人需要操作说明，公开听众主要想知道自己在听什么。', [
 ('A listening-session post|一次听音活动帖子', 'This week’s recording has rain on the roof in the quiet bit. We kept it. Headphones recommended.|这周录音安静那段有雨打屋顶的声音，我们留着了。推荐戴耳机听。'),
 ('A private file handoff|私下交文件', 'Here’s the lighter download. Same lesson, smaller file; the chapter marks are in the PDF.|这是小一点的下载版，课程内容一样。章节位置在PDF里。'),
 ('A credit correction|一次署名更正', 'Cello on the last track is Nia. My first caption gave that part to the wrong player; it’s corrected now.|最后一首的大提琴是Nia拉的。第一版文案把那段记给另一位演奏者了，已更正。')]),
 't1-04': ('Priya', 'I coordinate creator meetups at hotels. I am courteous and direct, especially with drivers and reception staff. Guests should get a usable place and time, with only the background they need.|我协调酒店里的创作者聚会。对司机和前台礼貌、直接，给客人能照着走的地点和时间，只补必要背景。', [
 ('A meetup notice|聚会通知', 'We’re in the courtyard room tonight. Come through reception and follow the blue signs; I’ll be at the desk from six.|今晚在庭院厅，从前台进，跟蓝色指示牌走。我六点起在签到台。'),
 ('A private driver message|私下联系司机', 'Please keep the 17:10 pickup. Two guests have already planned their trains around it.|请保留17:10接车，两位客人已经按这个时间安排火车了。'),
 ('An entrance correction|一次入口更正', 'The map pin led to the service entrance. I’ve moved it to the guest entrance and sent the new pin to today’s arrivals.|地图点位落在员工入口了，我改到了客人入口，也把新点位发给今天来的人。')]),
 't2-01': ('Mara', 'I run the event desk for an independent publishing fair. I speak gently without using pet names. In a private help conversation I give a short update about what is happening, and leave personal explanations there.|我值守独立出版市集的活动号。语气温和，不用亲昵称呼。私下求助时简短说进展，个人原因留在原会话。', [
 ('A fair-day public post|市集当天公开帖', 'The reading corner is open. There are a few cushions left; feel free to take one rather than sit on the cold floor.|阅读角开啦，还有几只坐垫，拿一只吧，别坐冷地板。'),
 ('A private participant reply|私下答参与者', 'You can tell me here. There’s no need to explain it to the whole group.|在这里告诉我就好，不用对整个群解释。'),
 ('An earlier help update|以前的一次帮助进展', 'I’ve reached the front desk. They’re bringing another chair over; I’ll let you know when it’s there.|联系上前台了，他们在搬另一把椅子。我等椅子到再告诉你。')]),
 't2-02': ('June', 'I organise a café discussion club. I usually answer the practical question first and keep explanations short. A disappointed voter deserves an explanation of the decision, without a lecture or someone else’s private circumstances.|我组织咖啡馆讨论会。通常先回答眼前问题，再简短解释。没选到心仪场地的人可以知道决定依据，不用听训话，也不需要知道别人的私事。', [
 ('A discussion invitation|讨论会邀请', 'Sunday, two o’clock. No homework this time—bring one sentence you disagreed with and we’ll start there.|周日两点。这次没作业，带一句你不同意的话来，我们从那聊起。'),
 ('A private venue question|私下问场地', 'Could you send the entrance photo from the street? The one on the listing starts inside the lobby.|能发张从街边看入口的照片吗？页面上那张已经拍到大厅里面了。'),
 ('A booking update|一次订场更新', 'We have the smaller room this week. Same start time; the updated directions are in the event card.|这周用小房间，开始时间不变。活动卡里的路线已更新。')]),
 't2-03': ('Theo', 'I host an offline game group. In casual posts I tease the equipment, not the players. When someone asks for help, I slow down, ask only what is needed, and make the next step clear.|我组织线下游戏局。闲聊时可以拿设备开玩笑，不拿玩家开玩笑。有人求助就认真些，只问必要的事，把下一步说清。', [
 ('A game-night post|游戏夜帖子', 'Three controllers, two working cables, one heroic roll of tape. We’re ready for Friday.|三个手柄、两条能用的线、一卷英勇的胶带。周五能开局了。'),
 ('A private seating reply|私下答座位问题', 'The end seat is free. If you’d rather stay where you are, that’s fine too.|边上那个座位空着。你想留在现在的位置也可以。'),
 ('A noise update|一次噪声处理进展', 'We turned the demo speaker down. Tell the desk if it’s still drowning out your table.|演示音箱调低了，要是你们桌还是听不清，跟服务台说一声。')]),
 't2-04': ('Sam', 'I coordinate exercise workshops and their streams. My public instructions are calm and plain. Staff messages can be technical, but I describe what changed so the next person can take over.|我协调运动工作坊和直播。公开指引平实、冷静。给工作人员可以说技术细节，但要交代改过什么，让下一班接得上。', [
 ('A workshop update|工作坊通知', 'Bring a towel and a bottle of water. We have mats, so you can leave yours at home.|带毛巾和水就行，现场有垫子，不用背自己的。'),
 ('A private operator handoff|私下交接给操作员', 'The left mic is muted in the mixer. Please check that channel before replacing the battery.|左边话筒在调音台静音了，换电池前先看那个通道。'),
 ('An archive correction|一次回放更正', 'The first upload cut off the last stretch. The full ending is in the replacement replay now.|第一次上传漏了最后的拉伸，替换后的回放已经补上完整结尾。')]),
 't3-01': ('Ellis', 'I lead local walks. My directions are short and I sometimes make a dry joke about the weather. When somebody is already on the way, give them the next useful turn rather than a long explanation.|我带本地徒步，路线说得简短，偶尔拿天气开个冷笑话。别人已经在路上时，先告诉他下一段怎么走，不发长篇解释。', [
 ('A walk report|一次徒步记录', 'The view was mostly cloud. The thermos, however, performed brilliantly.|风景基本是云。保温壶倒是发挥得很好。'),
 ('A private direction reply|私下答路线', 'Stay by the kiosk. I’ll come down the steps to you; don’t follow the group into the car park.|先在小卖部门口等，我下台阶来找你。别跟着人群往停车场走。'),
 ('An old route correction|以前的路线更正', 'I labelled the south gate as the east gate. Fixed the map. If you saved the old one, please replace it.|我把南门标成东门了，地图已改。存过旧图的话换一下。')]),
 't3-02': ('Ren', 'I look after a small dance programme’s credits and handouts. I write warmly and use the names contributors choose for public work. Similar names are a reason to check the record, never a joke at their expense.|我维护小型舞蹈项目的署名和手册。语气友好，公开使用贡献者选择的名字。名字相近就核记录，不拿这件事开玩笑。', [
 ('A programme post|节目介绍帖', 'Tonight’s final piece started as a five-minute rehearsal exercise. It escaped and became a whole dance.|今晚最后一支舞本来是个五分钟排练练习，后来没收住，长成了整支舞。'),
 ('A private credit question|私下问署名', 'Do you want your full name or the shorter version in the programme? I can change that line before it goes to print.|节目单上用全名还是简称？付印前我能改这一行。'),
 ('A role correction|一次贡献角色更正', 'Costumes were made by the workshop team; styling was Ada’s. I’ve separated those credits in the handout.|服装由工作室团队制作，造型是Ada负责的。手册里已把两项署名分开。')]),
 't3-03': ('Tate', 'I share car photography tutorials. I enjoy talking about the shot, but a person’s privacy request gets a straightforward response. Corrections say which copy changed, in everyday language.|我分享汽车摄影教程，喜欢聊怎么拍。别人提出隐私要求时就直接处理，改了哪份用日常话说清楚。', [
 ('A photo post|一条摄影帖', 'Wet tarmac does half the work here. The other half is me trying not to put my own reflection in the door.|湿路面帮了半个忙，另一半是我努力别让车门映出自己。'),
 ('A private edit reply|私下答修改请求', 'I see the number you mean. I’ll blur that spot and send you the updated preview.|我看到你说的号码了，我把那一处糊掉，发新版预览给你。'),
 ('A tutorial correction|一次教程更正', 'The crop in the download was older than the one in the post. I’ve replaced the download too.|下载包里的裁图比帖子那张旧，下载包也换好了。')]),
 't3-04': ('Isla', 'I host home-design meetups. I write welcoming notices and fairly spare private messages. People should know where to go without having their personal arrangements announced to everyone.|我组织家居设计聚会。公开通知友好些，私信则简洁。让人知道去哪儿就好，不把个人安排广播给所有人。', [
 ('A meetup post|一次聚会帖', 'We found enough chairs. That is the first design problem solved. See you on Saturday.|椅子够了，第一个设计问题解决了。周六见。'),
 ('A private guest reply|私下答客人', 'You’re already on the list. Just give the desk your booking code; you don’t need to queue again.|名单里有你，给服务台看预约码就行，不用重新排队。'),
 ('A room update|一次房间变更', 'The talk moved upstairs, but the materials table is still by the original door.|分享会搬到楼上了，材料台还在原来的门旁。')]),
 't4-01': ('Wren', 'I run a crochet group. I like plain, encouraging replies and concrete pointers to the right file. I credit patterns carefully and don’t treat a maker’s generosity as permission for everything.|我组织钩织小组，回复平实、鼓励些，直接指到该用的文件。图解署名认真写，不把作者大方当成什么都能用。', [
 ('A crochet tip|一条钩织提示', 'If the flower is turning into a tiny bowl, count the stitches in round three. Mine tried that too.|花朵快变成小碗的话，数一下第三圈针数。我那朵也闹过。'),
 ('A private file reply|私下答文件问题', 'The photo is in the first folder. The editable chart is a different file; I’ll check with its maker before sending it.|照片在第一个文件夹，可编辑图表是另一个文件。我先问作者再发。'),
 ('A pattern credit|一次图解署名', 'The leaf shape is Jo’s design, used here with permission. The slightly wonky stem is all mine.|叶子是Jo设计的，这里经她同意使用。歪歪的茎是我自己的发挥。')]),
 't4-02': ('Davi', 'I manage a community music-practice account. I am informal in rehearsal posts and calm when something needs checking. I explain a recording decision using the session facts, without turning a private report into gossip.|我管理社区音乐练习账号。排练帖可以随意，有事要核实就冷静些。用场次事实解释录制决定，不把私下报告变成八卦。', [
 ('A practice post|练习帖', 'We finally got through the bridge without stopping. Then the kettle clicked. Keeping that take anyway.|终于一口气过了桥段，水壶又咔哒响了。那条我们还是留着。'),
 ('A private checking message|私下核实消息', 'Which part of the clip do you mean? A rough time is enough; you don’t have to post it in the group.|你说的是片子哪一段？大概时间就行，不用发到群里。'),
 ('A replay update|一次回放更新', 'I trimmed the long setup at the start. The actual piece is still there from the first note.|开头很长的准备过程剪掉了，曲子从第一声起都留着。')]),
 't4-03': ('Arin', 'I produce small concert releases. My messages to collaborators are friendly and specific about the version and destination. Public copy can have a little excitement; a licensing question needs an unembellished answer.|我制作小型音乐会发布内容。给合作者的消息友好，具体说版本和去向。公开文案可以兴奋一点，许可问题就直接答。', [
 ('A concert post|音乐会帖子', 'There’s a moment near the end when the whole room stops shuffling. You can hear it in the recording.|快结束时有一刻，全场都不再窸窸窣窣了，录音里听得出来。'),
 ('A private partner handoff|私下交给合作方', 'Use the shorter cut for the foyer. The longer interview belongs in the member download, not on that screen.|门厅用短版，长采访放会员下载包，不放那块屏幕。'),
 ('An earlier release correction|以前的发布更正', 'The venue screen had yesterday’s opening time. They’ve replaced the file; tonight’s card now says 19:00.|场馆屏幕播的还是昨天的开门时间。他们已换文件，今晚卡片写19:00。')]),
 't4-04': ('Noor', 'I organise museum club visits. I give exact meeting places and handle booking money carefully. I can be brisk with a deadline, while staying polite to staff and members.|我组织博物馆社群活动。集合地点说准确，订场费用认真处理。有截止时间时说话利落些，对工作人员和成员仍然礼貌。', [
 ('A visit notice|参观通知', 'Meet by the cloakroom at 13:40. The sculpture court is the visit, not the meeting point—I confused that last time.|13:40衣帽间旁集合。雕塑庭院是参观地点，不是集合点，上次我说混了。'),
 ('A private booking reply|私下答订场', 'Please keep the existing hold while you check the other room. I don’t want us paying for two.|你核另一间时先保留原预留，我不想两间都付费。'),
 ('A payment update|一次付款进展', 'The refund reached the club account this morning. I’ve sent the receipt to the treasurer.|退款今早到社团账户了，回执已经发给财务同学。')]),
 't5-01': ('Mei', 'I run a cooking-study group. My posts are lively, but I explain votes and bookings in plain terms. When the information changes, I say what changed without blaming people for following the old notice.|我组织边做饭边学习的小组。发帖活泼些，投票和订场用白话讲。信息变了就说改了什么，不怪按旧通知办事的人。', [
 ('A cooking-study post|一次做饭学习帖', 'Bring your notes and an appetite. We’ll argue about the chapter while the onions soften.|带笔记，也带胃口。洋葱炒软的工夫正好争论一下那章。'),
 ('A private booking reply|私下答订场', 'That was the right room on yesterday’s list. I’ll check the revised list before changing your hold.|按昨天名单那间没选错。我看完修订名单再改你的预留。'),
 ('A public poll correction|一次公开投票更正', 'Two entries were duplicates. I removed the extra votes and updated the total; your actual vote is still counted.|有两条重复记录，多出的票去掉了，总数已更新。你实际投的那票还在。')]),
 't5-02': ('Kit', 'I host animation screenings. I like a relaxed welcome and short, reassuring private replies. I take a changed preference seriously; people do not owe the group a personal explanation.|我主持动画放映，欢迎帖轻松，私信简短、让人安心。别人改了意愿就认真照办，不要求对全群解释私事。', [
 ('A screening post|放映欢迎帖', 'Doors open at six. The subtitles have passed the back-row test: I stood there and squinted.|六点开门，字幕通过了后排测试：我站在那里眯眼看过了。'),
 ('A private change request|私下改安排', 'Of course, you can stay where you are. I’ll tell the usher you no longer need the seat change.|当然，你可以留原位。我会跟引导员说不用换座了。'),
 ('An earlier floor update|以前的现场更新', 'The aisle light is back on. You can leave through that door again; the side door is still available too.|过道灯亮了，那扇门可以走，侧门也还开着。')]),
 't5-03': ('Tess', 'I coordinate a maker fair’s volunteer desk. I write concise handovers and warmer replies to visitors. Another person taking over a task is useful news, but I wait for their result before saying it is done.|我协调创客市集志愿服务台。交接写简洁，答访客温和些。有人接手是进展，但要等结果才说办好了。', [
 ('A volunteer public post|志愿者公开帖', 'Thanks for getting the soldering table packed away. We found the missing cable underneath the biscuit tin.|谢谢收好焊接台。那条失踪的线在饼干盒底下找到了。'),
 ('A private visitor reply|私下答访客', 'I can pass on the aisle you mentioned. I’ll leave your message and name in this thread.|你说的过道我可以转给现场，原消息和名字留在这条私信里。'),
 ('A shift handover|一次值班交接', 'The morning team has checked the front tables. The back row is still waiting; Jules has accepted that job.|早班查过前面几排桌子，后排还没查，Jules接了后排这项。')]),
 't5-04': ('Sol', 'I organise shared cooking sessions. Food and transport arrangements get clear, practical wording. In public I keep the mood friendly; private access or dietary details stay with the people handling them.|我组织一起做饭的活动，食材和交通安排说清楚、能照办。公开语气友好，个人通行或饮食细节只给需要处理的人。', [
 ('A cooking invitation|做饭邀请帖', 'We’re making enough dumplings to justify getting the big table out. Bring a container for leftovers.|这次饺子够多，值得搬大桌子。带个饭盒装剩下的吧。'),
 ('A private supplier message|私下联系供货方', 'The kitchen can take the chilled box after four. Please wait for the loading-bay contact before unloading.|厨房四点后能收冷藏箱。卸货前请等装卸口联系人接应。'),
 ('An earlier delivery update|以前的配送进展', 'The driver has handed the box to the kitchen team. They’ve checked it into the cold room; we can stop chasing that one.|司机把箱子交给厨房了，他们已收进冷库。这一项可以不用再追了。')]),
}

def profile_for(sid, default_profile, default_history):
    if sid not in PROFILES:
        return deepcopy(default_profile), deepcopy(default_history)
    name, prose, history = PROFILES[sid]
    profile = deepcopy(default_profile)
    profile.update(display_name=name, text=prose, user_id='creator', role='creator', history_origin='synthetic')
    return profile, deepcopy(history)
