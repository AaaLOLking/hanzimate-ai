// Chinese dictionary — source of truth for every in-scope UI string.
// Keys are dot-namespaced by surface: nav.*, shell.*, home.*, practice.*.

export const zh = {
  // Sidebar navigation (labels mirror lib/navigation.ts).
  "nav.home": "今日",
  "nav.conversation": "对话训练",
  "nav.courses": "系统课程",
  "nav.reviews": "今日复习",
  "nav.errors": "错误本",
  "nav.profile": "学习档案",
  "nav.beta": "体验反馈",

  // AppShell chrome.
  "shell.brandTagline": "中文学习空间",
  "shell.mainNavAria": "主导航",
  "shell.openNav": "打开导航菜单",
  "shell.closeNav": "关闭导航菜单",
  "shell.profileFallback": "尚未完成建档",
  "shell.openProfile": "打开学习档案",
  "shell.langLabel": "界面语言",
  "shell.langZh": "中文",
  "shell.langEn": "EN",

  // Home: header.
  "home.eyebrow": "今日计划 · 15 分钟",
  "home.headline": "把学过的中文，用在今天",
  "home.modelFallback": "文本模型待连接",
  "home.settings": "学习设置",
  "home.apiOffline": "API 尚未连接。请先启动 FastAPI 服务，再刷新页面。",
  "home.setupLead": "，再为你生成合适的中文学习任务。",
  "home.setupStrong": "先用 3 分钟认识你",
  "home.setupCta": "开始建档 →",

  // Home: mission card.
  "home.missionFallback": "建立你的第一个中文目标",
  "home.missionDescFallback": "完成 3 分钟建档后，AI 会生成适合你的第一个学习空间。",
  "home.reviewedToday": "今日已复习",

  // Home: review section.
  "home.reviewTitle": "先唤醒旧知识",
  "home.reviewCtaSuffix": " 项到期 · 进入复习 →",
  "home.reminderLead": "到了你设置的复习时间，今天有 ",
  "home.reminderTail": " 项旧知识等你回顾。",
  "home.reviewNow": "现在开始 →",
  "home.dueNow": "现在可复习",
  "home.cardCopy": "先独立作答，再查看反馈。",
  "home.cardCta": "开始回顾 →",
  "home.noDueNext": "目前没有到期内容。下次安排：",
  "home.noDue": "还没有到期复习。确认对话中的错误后，会自动加入计划。",

  // Home: conversation card.
  "home.liveTitleFallback": "日常中文",
  "home.liveSuffix": " · 场景练习",
  "home.liveCopy": "AI 每轮最多纠正一个重点。你可以随时插话，也可以说“慢一点”。",
  "home.metaDuration": "◷ 8 分钟",
  "home.metaSpeed": "◎ 正常语速",
  "home.metaLang": "中 / EN",
  "home.start": "开始对话",
  "home.startLocked": "先完成建档",

  // Home: memory preview.
  "home.memoryTitle": "AI 为什么记住这个？",
  "home.memoryCta": "查看全部记忆 →",
  "home.evidence": "已确认 · 证据可追溯",
  "home.confirmedTimes": "已确认 {count} 次",
  "home.noMemory": "暂无已确认记忆。AI 提出的错误需要你确认后才会保存。",

  // Home: coach panel.
  "home.coachName": "小文老师",
  "home.coachRole": "学习向导",
  "home.panelLabel": "学习向导",
  "home.nextLabel": "接下来做什么",
  "home.dueCopy": "有 {count} 项已确认错误到期，先花几分钟回顾。",
  "home.noDueCopy": "没有到期复习时，继续一节课或开始一次场景对话。",
  "home.tip1": "复习时先独立作答，再看反馈。课程里遇到问题，可以直接向课内老师提问。",
  "home.tip2": "这里是学习入口，不是实时聊天框。",
  "home.gotoReviews": "进入今日复习",
  "home.gotoCourses": "选择一节课程",
  "home.privacyTitle": "学习记录由你掌控",
  "home.privacyCta": "查看错误本",

  // Home: workspace sidebar.
  "home.workspacesTitle": "最近的学习空间",
  "home.newWorkspace": "新建学习空间（即将开放）",
  "home.soon": "即将开放",
  "home.kindConversation": "对话",
  "home.kindLesson": "课程",
  "home.kindReview": "复习",
  "home.statusActive": "进行中",
  "home.statusReviewDue": "待复习",
  "home.statusCompleted": "已完成",
  "home.statusProcessing": "处理中",
  "home.emptyWorkspaces": "完成建档后，这里会出现你的第一个学习空间。",

  // Practice page.
  "practice.eyebrow": "对话训练 · 选择练习方式",
  "practice.title": "今天想怎么练中文？",
  "practice.livePill": "实时口语",
  "practice.apiOffline": "API 尚未连接。请先启动 FastAPI 服务，再刷新页面。",
  "practice.loading": "正在读取练习场景…",
  "practice.modeScenario": "场景练习",
  "practice.modeScenarioCopy": "从生活场景里选一个，完成一个具体任务。",
  "practice.modeFree": "自由对话",
  "practice.modeFreeCopy": "聊任何感兴趣的话题，也可以让小文找话题。",
  "practice.modeCustom": "自定义目标",
  "practice.modeCustomCopy": "按你的需求练习，比如面试自我介绍。",
  "practice.scenarioTitle": "选择一个场景",
  "practice.freeCopy": "从今天的经历、兴趣或任何想聊的话题开始。小文会陪你自然交流，并在每轮最多纠正一个重点。",
  "practice.customLabel": "你想练习什么？",
  "practice.customPlaceholder": "例如：明天我要面试，请扮演面试官，帮我练习中文自我介绍。",
  "practice.customCounter": "{count}/500 字 · 开始后本次目标固定，下次练习可修改。",
  "practice.startVoice": "使用麦克风开始",
  "practice.startText": "先用文字演练",
  "practice.starting": "正在创建练习…",
  "practice.customRequired": "请先填写你想练习的目标。",
  "practice.scenarioRequired": "请选择一个练习场景。",
  "practice.createFailed": "创建练习失败，请重试。",

  // Practice: panel.
  "practice.panelLabel": "练习设置",
  "practice.coachName": "小文老师",
  "practice.coachRole": "实时口语教练",
  "practice.objectiveLabel": "本次目标",
  "practice.objectiveScenarioFallback": "选择一个场景后，这里会显示本次目标。",
  "practice.objectiveFree": "围绕你感兴趣的话题自然交流，可以随时换话题。",
  "practice.objectiveCustomFallback": "填写你想练习的目标后，这里会显示本次目标。",
  "practice.correctionLabel": "纠错模式",
  "practice.correctionImmersion": "沉浸 · 最少干预",
  "practice.correctionCoach": "教练 · 每轮一个重点",
  "practice.correctionExam": "考试 · 结束后反馈",
  "practice.startersLabel": "可以这样开始",
  "practice.safetyTitle": "场景边界",
  "practice.privacyTitle": "音频不落盘",
  "practice.privacyCopy": "只保存可靠文字转写和必要会话事件。",

  // Practice: sidebar.
  "practice.back": "← 返回今日计划",
  "practice.sideLabel": "PRACTICE",
  "practice.sideTitle": "对话训练",
  "practice.sideCopy": "选一种方式开始。开始后可以打断、插话，也可以随时切换到文字。",
} as const;

export type I18nKey = keyof typeof zh;
