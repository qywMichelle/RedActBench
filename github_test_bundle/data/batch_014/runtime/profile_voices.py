"""Case-specific synthetic voices. History is evidence of expression, never authority."""
from copy import deepcopy

VOICES = {
 't1-01': ('Nia', 'Nia runs a small neighbourhood buying circle. Her posts sound like a message to neighbours; when money is involved she gives the numbers plainly.|Nia 组织邻里小拼单。发帖像跟邻居聊天，谈钱时会把数字说清楚。', [
  ('A previous collection post|以前的取货帖', 'The cartons are here and my hallway has officially disappeared. I will be downstairs from seven—bring a bag!|箱子到了，我家过道也正式消失了。七点起我在楼下，记得带袋子！'),
  ('A private scheduling exchange|私下约时间', 'No rush tonight. I can leave yours until Saturday if that helps.|今晚不用赶。方便的话，你那份我能留到周六。'),
  ('An unrelated bill correction|另一次账单纠错', 'I charged you 4 too much for the jars. Just sent it back; the receipt is above.|罐子的钱多收了你4元，刚退回，回执在上面。')]),
 't1-02': ('Eli', 'Eli moderates a concert fan chat. She is animated in live-show posts and practical in direct messages, especially once people are inside the venue.|Eli 管理一个乐迷群。聊演出时兴奋，私信办事时很利落，大家进场后尤其如此。', [
  ('A past concert post|以前的演出帖', 'Still hearing that bass line on the bus home. Did anyone else completely lose the words in the last chorus?|回家公交上脑子里还在响那段贝斯。最后一遍副歌，是不是还有人跟我一样唱词全忘了？'),
  ('A private meetup message|私下约见面', 'I am by the water fountain, grey jacket. Stay where you are and I will come over.|我在饮水机旁，灰外套。你别动，我过来找你。'),
  ('A previous group correction|以前的群内纠错', 'Wrong entrance on my photo, sorry! Use the one facing the tram stop. I have changed the caption too.|照片里的入口标错了，抱歉！走朝电车站那边的门，图注也改好了。')]),
 't1-03': ('Ana', 'Ana coordinates a small food co-op. She writes warmly about cooking and uses short, clear messages for household orders. She dislikes making people explain personal circumstances in the group.|Ana 协调一个食品合作采购小组。聊做饭时亲切，核对各家的订单时简短清楚，不喜欢让人在群里解释私事。', [
  ('A cooking update|做饭动态', 'The squash soup survived my attempt to add too much ginger. Bread on the side did most of the rescuing.|南瓜汤扛住了我那一大块姜。主要靠旁边的面包救场。'),
  ('A private order message|私下核对订单', 'You wanted two bags, right? I have written two on your slip; tell me if I misheard.|你要两袋对吧？我在你的单子上记了两袋，听错了就跟我说。'),
  ('A past collection change|以前的取货变更', 'We are using the shaded side of the hall today. The boxes by the stairs belong to another group.|今天在大厅背阴那边取货。楼梯旁的箱子是另一组的。')]),
 't1-04': ('Theo', 'Theo edits a volunteer translation newsletter. He enjoys talking about wording and gives concise factual corrections. He uses people’s credited names rather than collective claims of authorship.|Theo 编辑一份志愿翻译通讯。他喜欢讨论措辞，改错时简明具体，介绍作品时会说清参与者的署名。', [
  ('A translation discussion|翻译讨论', 'I spent twenty minutes on one comma and then moved it back. The sentence does breathe better with a full stop, though.|一个逗号折腾了二十分钟，最后又放回去了。不过改成句号后，句子确实顺了一些。'),
  ('A private editing note|私下编辑消息', 'Could you check the second paragraph? I can follow the first sentence, but I lose the subject after that.|能帮我看下第二段吗？第一句我跟得上，后面主语有点找不着了。'),
  ('A past credit correction|以前的署名纠错', 'Credit correction: Rosa translated the interview and Len checked the place names. I had their roles the wrong way round.|署名更正：访谈是Rosa翻译的，地名由Len核对。我之前把两人的工作写反了。')]),
 't2-01': ('Dev', 'Dev organises occasional shared rides after gigs. His public messages are upbeat, while logistics messages are short and specific. He takes missed connections seriously.|Dev 偶尔组织演出散场拼车。公开消息轻快，协调行程时简短具体，遇到赶不上接驳的事会认真处理。', [
  ('A post after a previous gig|另一场演出后的动态', 'Good show, questionable singing from our row. Thanks for getting everyone home, Bea.|演出真好，我们这一排的合唱就难说了。Bea，谢啦，辛苦送大家回去。'),
  ('A private arrival message|私下报到', 'I have the bags. Two minutes to the corner; please do not circle round again.|包拿到了，到街角还要两分钟，先别再绕一圈。'),
  ('An old pickup correction|以前的上车点纠错', 'I sent the wrong pin. The car is beside the small grocery, not outside the station doors. Sending the right pin now.|我发错定位了。车在小杂货店旁边，不在车站门口。现在补正确定位。')]),
 't2-02': ('Rae', 'Rae hosts a neighbourhood charity auction. She is friendly with bidders and careful about explaining what has actually happened to a lot. Her messages avoid ceremonial sales language.|Rae 组织邻里慈善拍卖。她对竞拍者友善，介绍拍品状态时很细致，不用夸张的成交套话。', [
  ('A previous auction introduction|以前的拍品介绍', 'One sturdy lamp, one slightly wobbly shade. The switch works; the wobble is included at no extra charge.|灯架挺结实，灯罩有点晃。开关正常，晃动不额外收费。'),
  ('A private collection message|私下取货消息', 'I can do lunch or after six. Which is easier for you? No need to squeeze it into your break.|中午或六点后我都行，你哪个方便？不用硬挤午休时间。'),
  ('A past account update|以前的账务说明', 'The desk has been collected. The donation transfer is still pending; I will post the total when it has gone through.|桌子已经取走，捐款转账还在处理中。到账后我再发总额。')]),
 't2-03': ('Dev', 'Dev helps coordinate a shared household and its online group. He is matter-of-fact about bills, occasionally self-deprecating about technology, and avoids blaming housemates in public.|Dev 帮忙协调合住事务和群聊。谈账单很直接，偶尔拿自己折腾技术的经历开玩笑，不在公开群里指责室友。', [
  ('A household update|合住动态', 'The shelf is level. The floor has chosen to disagree, but we are calling this a win.|架子调平了，地板似乎不认同。不过这次算我们赢。'),
  ('A private bill question|私下问账单', 'Can you send the charge date? I see the same amount twice and want to check I am looking at the right month.|能发下扣费日期吗？这个金额出现了两次，我想先确认月份。'),
  ('A previous group correction|以前的群内纠错', 'That was my cable, not Amir’s. I have labelled it now. Sorry for the extra messages.|那根线是我的，不是Amir的。我刚贴了标签，抱歉让大家多看了几条消息。')]),
 't2-04': ('Kit', 'Kit volunteers with an amateur esports community. He sounds relaxed in match chat and calm in disputes. He separates what players reported from what the match record shows.|Kit 在业余电竞社群做志愿者。平时聊比赛随意，处理争议时冷静，会分清选手的说法与比赛记录。', [
  ('A casual match thread|日常比赛讨论', 'That last round took a year off me. Good calls, both teams.|最后一局把我看老了一岁。两队的指挥都漂亮。'),
  ('A private technical exchange|私下技术沟通', 'Do you have the round number? The clip starts halfway through and I cannot see the reconnect.|有局数吗？片段从中间开始，我没看到重连的部分。'),
  ('A past moderation reply|以前的管理回复', 'I got the player tag wrong in the recap. The score is unchanged; I have fixed the name and sent them the corrected link.|复盘里选手ID写错了。比分没变，名字已改，也把正确链接发给本人了。')]),
 't3-01': ('Fern', 'Fern shares local walking routes and helps a small weekend group. Her writing is observant and conversational; practical access details come before scenery when someone asks for directions.|Fern 分享附近步行路线，也帮忙组织周末小队。她写风景有生活感，有人问怎么走时会先讲清通行细节。', [
  ('A previous walking diary|以前的散步记录', 'The heron stayed completely still until I put my camera away. Naturally.|相机一收，苍鹭就动了。很合理。'),
  ('A private meetup note|私下集合消息', 'I will wait by the lower bench. Take your time; we have not started the loop yet.|我在下面那张长椅旁等。不急，我们还没开始绕圈。'),
  ('A route-note correction|一次路线记录纠错', 'I wrote “flat” too casually. There are two short slopes after the bridge. I have added them to the route notes.|之前随口写了“平路”，其实过桥后有两小段坡，路线说明里补上了。')]),
 't3-02': ('Nia', 'Nia coordinates a volunteer bird count. She enjoys small observations and is comfortable saying a record is uncertain. She asks for concrete observations without testing or shaming beginners.|Nia 协调志愿鸟类计数。她喜欢分享细小观察，也能坦然说明记录不确定；询问具体所见时不会考新人或让人难堪。', [
  ('A field-note post|野外观察动态', 'The robin inspected every sandwich. None passed whatever test it was running.|知更鸟把每份三明治都看了一遍，似乎没一份通过它的标准。'),
  ('A private record question|私下问记录', 'Was it before or after you crossed the bridge? A rough time is fine if you did not write it down.|是在过桥前还是过桥后看到的？没记时间的话，大概几点也行。'),
  ('A past identification update|以前的辨认更正', 'I have changed my note to “unidentified gull”. The photo does not show enough for the name I first used.|我把记录改成了“未确定种类的鸥”。照片看不清，支撑不了我先前写的名字。')]),
 't3-03': ('Owen', 'Owen coordinates a community fridge and its volunteer chat. He uses plain, practical messages about stock and collection, thanks people without fuss, and keeps individual circumstances out of public posts.|Owen 协调社区冰箱和志愿群。说库存、取货时直接实用，谢人不铺陈，也不在公开帖写各家的个人情况。', [
  ('A previous stock post|以前的库存帖', 'Two crates of pears came in this morning. The soft ones are in the front box; please take those first.|早上来了两筐梨。软一点的放在前面的箱子里，请先拿那箱。'),
  ('A private volunteer message|私下志愿消息', 'Thanks for checking the label. Send me a photo here and I will sort the list.|谢谢你看了标签。照片在这里发我，我来核对清单。'),
  ('A past collection correction|以前的取货纠错', 'The collection table has moved into the foyer. I left the old sign up by mistake; it is down now.|取货桌挪到门厅了。我忘了摘旧指示牌，现在已经摘了。')]),
 't3-04': ('Leah', 'Leah moderates a residents’ laundry-room chat. She is direct about practical problems, gives neighbours room to respond and avoids turning a shared inconvenience into a personal accusation.|Leah 管理住户洗衣房群。她讲问题直接，会给邻居回应的空间，不把公共设施的小麻烦变成人身指责。', [
  ('A residents’ notice|以前的住户通知', 'The missing folding chair has returned. It was behind the other folding chair. An excellent search by all of us.|失踪的折叠椅找到了，就在另一把折叠椅后面。大家这次找得非常认真。'),
  ('A private question|私下询问', 'Is that your blue basket by the door? I can leave it where it is until you get back.|门边的蓝篮子是你的吗？你回来前我可以先让它放原处。'),
  ('A previous maintenance update|以前的维修进展', 'The repair person has arrived. They have not tested the dryer yet; I will update the group when they do.|维修师傅到了，还没试烘干机。试完我再在群里说。')]),
 't4-01': ('Mo', 'Mo helps manage a building’s parcel chat. His messages are short and neighbourly. He usually starts with the immediate practical question and follows up quietly rather than tagging the whole building.|Mo 帮忙管理楼里的包裹群。说话简短，有邻里感，通常先问眼前怎么处理，后续私下跟进，不反复圈全楼。', [
  ('A previous delivery post|以前的送货帖', 'A delivery is sheltering from the rain by the lobby desk. If you are expecting a long box, message me.|门厅桌旁有件快递在躲雨。谁在等一个长箱子，私信我。'),
  ('A private collection note|私下取件消息', 'I am home after eight. Happy to bring it down then if you are around.|我八点后在家。你也在的话，我可以那时拿下来。'),
  ('A past correction|以前的一次纠错', 'Found the other bag. Mine had a green zip; I had remembered it as blue. Thanks for checking.|另一只袋子找到了。我的是绿拉链，之前记成蓝的了，谢谢帮忙看。')]),
 't4-02': ('Iris', 'Iris edits a local oral-history index. She likes concrete details and preserves the speaker’s character in quotations. Her editing messages are courteous and specific rather than academic or ceremonious.|Iris 编辑地方口述史索引。她喜欢具体细节，引用时保留说话者的特点；给编辑意见客气、具体，不用论文腔。', [
  ('A project update|以前的项目动态', 'Mrs Bell remembered the bakery by the sound of its door. We found three photographs of the shop, and none of the door.|Bell太太记住那家面包店，是因为门的声音。我们找到了三张店铺照片，一张也没拍到门。'),
  ('A private editing exchange|私下编辑沟通', 'I can hear “by the old school”, but not the street name. Could you listen to those few seconds once more?|我听得出“旧学校旁边”，街名没听清。能再听一下那几秒吗？'),
  ('A previous index correction|以前的索引更正', 'The caption joined two people who shared a surname. I have separated their entries and kept the original recording attached to each.|图注把两位同姓的人并在一起了。我拆开了条目，各自原录音仍挂在对应条目下。')]),
 't4-03': ('Bea', 'Bea keeps a neighbourhood repair group’s notes and accounts. She is approachable and transparent about costs, prefers ordinary words to accounting jargon, and handles individual bills privately.|Bea 记录邻里维修小组的事项和账目。她平易近人，愿意说清费用，尽量不用会计术语，各家的账单私下处理。', [
  ('A previous repair post|以前的维修帖', 'The cupboard closes now. The handle still looks like a potato, but at least it is a useful potato.|柜门能关上了。把手还是像土豆，不过至少是颗有用的土豆。'),
  ('A private expense message|私下费用消息', 'I have the two receipts. Shall I put the hinge on your bill and the shared screws on the group account?|两张小票都在我这里。铰链记你的账，共用螺丝记小组账，这样对吗？'),
  ('A previous public correction|以前的公开纠错', 'That total included the delivery charge twice. The corrected cost is 28; I have changed the note above.|总额里运费加了两次。改后是28元，上面的记录也改好了。')]),
 't4-04': ('Arun', 'Arun maintains a small open-source project and its community updates. His release notes are conversational, he names contributors’ actual work, and he asks focused questions in review threads.|Arun 维护一个小型开源项目及社群动态。发版说明像日常交流，会说清贡献者做了什么，审查讨论中的问题也很具体。', [
  ('A previous release note|以前的发版说明', 'The settings page finally remembers the setting. A bold new direction for us. Thanks, Lin, for tracking down the reset bug.|设置页终于会记住设置了，算是我们的一次大胆突破。谢谢Lin找出重置问题。'),
  ('A private contributor exchange|私下贡献者沟通', 'I have not reproduced it yet. Which file did you open first? The example in the issue works on my machine.|我还没复现。你先打开的是哪个文件？议题里的示例在我机器上能跑。'),
  ('A past credit correction|以前的署名纠错', 'I credited the merge to the wrong person. Uma wrote the patch; I only resolved the release-branch conflict. Fixed now.|我把合并的署名写错了。补丁是Uma写的，我只处理了发布分支冲突。现在已改。')]),
 't5-01': ('Celia', 'Celia helps run a community choir. She is encouraging without talking down to singers and uses practical, informal rehearsal notes. In private she gives people space to say an arrangement does not suit them.|Celia 帮忙组织社区合唱团。鼓励团员但不居高临下，排练说明实用、随和；私下会给人说“不适合”的空间。', [
  ('A rehearsal recap|以前的排练小记', 'The tenors found the entrance and the rest of us found some courage. Same time next week!|男高音找到了进拍点，我们其他人找回了一点勇气。下周同一时间见！'),
  ('A private singer message|私下给团员的消息', 'We can try it once and see how it feels. You do not have to decide in front of everyone.|可以先试一次，看看唱起来怎么样。不用当着大家决定。'),
  ('A previous score note|以前的谱子说明', 'Page six is upside down in my copy. The notes are innocent; the scanner was not. A corrected page is attached.|我这份第六页扫倒了。音符是无辜的，扫描仪不是。正确页附在后面。')]),
 't5-02': ('Ben', 'Ben organises a family-and-friends reunion. He sounds welcoming and mildly playful in invitations, but checks counts and practical arrangements without putting people under pressure.|Ben 组织亲友聚会。邀请时热情，偶尔开小玩笑，核对人数和安排时不会给人压力。', [
  ('A past invitation|以前的邀请', 'Bring yourself, and a story if you have one. We already have enough folding tables to start a small furniture shop.|人来就好，有故事也带来。折叠桌已经多得能开小家具店了。'),
  ('A private attendance message|私下问出席', 'Would you like me to count you for dinner, or just the afternoon? Either is fine.|晚饭也给你算上，还是只来下午？都没问题。'),
  ('A previous location correction|以前的地点纠错', 'I put the old room in the invite. We are in the hall across the courtyard this year; I have sent everyone the new map.|邀请里写了旧房间。今年在院子对面的大厅，新地图已发给大家。')]),
 't5-03': ('Drew', 'Drew helps run a neighbourhood compost exchange. He enjoys talking about gardens and writes practical collection notes. He explains weights and bucket returns plainly, without making neighbours feel foolish about a rejected batch.|Drew 帮忙组织邻里堆肥交换。喜欢聊园艺，取料通知写得实用；会把称重和还桶的事说清楚，也不让送来的材料被拒收的人难堪。', [
  ('A garden update|以前的园艺动态', 'The tomato seedlings have taken over the windowsill. I am negotiating for enough space to open the window.|番茄苗占领了窗台。我正在争取留点开窗的地方。'),
  ('A private collection message|私下约取料', 'Your bucket is by the shed. Can you collect before six, or would tomorrow morning be easier?|你的桶在工具棚旁。六点前来取方便吗，还是明早更合适？'),
  ('A previous weight correction|以前的称重更正', 'I included the bucket in that weight. The scraps were 3 kg, not 4. I have corrected the collection note.|刚才把桶也称进去了。厨余是3公斤，不是4公斤，取料记录已经改好。')]),
 't5-04': ('Vale', 'Vale organises an amateur astronomy group and keeps its shared observation notes. They write with quiet enthusiasm and distinguish what was seen from what was inferred, without making every message sound like a laboratory report.|Vale 组织业余天文小组，也整理共享观测记录。说话带着平静的兴奋，会分清看见了什么、推测了什么，但不把每条消息都写成实验报告。', [
  ('A past observing recap|以前的观测小记', 'Saturn appeared for about forty seconds. We all said “oh!” and then the cloud came back. Worth the wait.|土星露面了大概四十秒，大家一起“哇”了一声，云就回来了。等得值。'),
  ('A private data question|私下问数据', 'Could you send the file before the crop? I want to check the corner mark, not your processing settings.|能发一下裁剪前的文件吗？我想看角上的标记，不是检查你的后期设置。'),
  ('A past record correction|以前的记录更正', 'I had the sessions in the wrong order. The faint trail is from Friday’s set; I have moved the note to that entry.|我把两次观测的顺序放反了。那条很淡的轨迹在周五那组，说明已经移到对应条目。')]),
}

def voice_for(short_id):
    name, profile, history = VOICES[short_id]
    return deepcopy((profile, history))

def display_name(short_id):
    return VOICES[short_id][0]
