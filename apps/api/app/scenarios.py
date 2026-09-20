from typing import TypedDict


class ConversationScenario(TypedDict):
    id: str
    title: str
    category: str
    level: str
    objective: str
    opening_line: str
    prompt_starters: list[str]
    safety_note: str | None


CONVERSATION_SCENARIOS: tuple[ConversationScenario, ...] = (
    {
        "id": "campus-canteen",
        "title": "食堂点餐",
        "category": "校园生活",
        "level": "HSK2–3",
        "objective": "点一份餐，说明数量或口味，并确认价格",
        "opening_line": "你好，想吃点什么？",
        "prompt_starters": ["我要一份宫保鸡丁。", "这个辣不辣？"],
        "safety_note": None,
    },
    {
        "id": "convenience-store",
        "title": "便利店购物",
        "category": "城市生活",
        "level": "HSK2–3",
        "objective": "询问商品位置、价格，并完成结账交流",
        "opening_line": "欢迎光临，需要帮你找什么吗？",
        "prompt_starters": ["请问，矿泉水在哪里？", "可以用手机支付吗？"],
        "safety_note": None,
    },
    {
        "id": "campus-directions",
        "title": "校园问路",
        "category": "校园生活",
        "level": "HSK2–3",
        "objective": "询问教学楼位置，并复述路线进行确认",
        "opening_line": "你好，你在找哪个地方？",
        "prompt_starters": ["请问，教学楼怎么走？", "所以我要在第二个路口右转，对吗？"],
        "safety_note": None,
    },
    {
        "id": "dorm-repair",
        "title": "宿舍报修",
        "category": "校园生活",
        "level": "HSK3–4",
        "objective": "描述宿舍设施问题，说明位置并约定维修时间",
        "opening_line": "你好，这里是宿舍服务台，请问有什么问题？",
        "prompt_starters": ["我房间的空调坏了。", "今天下午可以来修吗？"],
        "safety_note": None,
    },
    {
        "id": "hospital-registration",
        "title": "医院挂号",
        "category": "城市生活",
        "level": "HSK3–4",
        "objective": "说明就诊需求，询问科室和挂号流程",
        "opening_line": "你好，请问你想挂哪个科？",
        "prompt_starters": ["我想看医生，但是不知道挂哪个科。", "请问要先在哪里登记？"],
        "safety_note": "本场景只练习语言表达，不提供医疗诊断或治疗建议。",
    },
    {
        "id": "classroom-question",
        "title": "课堂提问",
        "category": "学术中文",
        "level": "HSK3–4",
        "objective": "礼貌打断老师，说明不理解之处并请求举例",
        "opening_line": "这部分大家听明白了吗？",
        "prompt_starters": ["老师，不好意思，我有一个问题。", "您可以再举一个例子吗？"],
        "safety_note": None,
    },
)


SCENARIOS_BY_ID = {scenario["id"]: scenario for scenario in CONVERSATION_SCENARIOS}
