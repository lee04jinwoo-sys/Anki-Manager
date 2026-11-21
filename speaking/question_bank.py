"""72 Daily English speaking questions (one question each). Everyday categories first."""
from __future__ import annotations

from typing import List, Optional

from speaking.models import DailyQuestion

DAILY_QUESTIONS: List[DailyQuestion] = [
    # --- Campus & Classes ---
    DailyQuestion(id="daily_001", category="Campus & Classes", prompt="Someone from another faculty asks what you study and why you chose it. What do you tell them?"),
    DailyQuestion(id="daily_002", category="Campus & Classes", prompt="You're in your professor's office hours because you're stuck on a problem. What have you tried so far, and where did you get stuck?"),
    DailyQuestion(id="daily_003", category="Campus & Classes", prompt="A teammate wants to rush your group project with sloppy shortcuts. How do you tell them you're concerned and suggest a better plan?"),
    DailyQuestion(id="daily_004", category="Campus & Classes", prompt="Which class are you enjoying most this semester, and why?"),
    DailyQuestion(id="daily_005", category="Campus & Classes", prompt="Someone in the library asks how midterm week is going. What do you say besides \"busy\"?"),
    DailyQuestion(id="daily_006", category="Campus & Classes", prompt="Your TA asks whether students rely too much on AI tools when learning the basics. What do you think?"),
    DailyQuestion(id="daily_007", category="Campus & Classes", prompt="An exchange student asks where you like to study on campus. Where do you go, and why?"),
    DailyQuestion(id="daily_008", category="Campus & Classes", prompt="What's an unexpected bug or snag that cost you hours on a recent lab, and how did you find it?"),
    DailyQuestion(id="daily_009", category="Campus & Classes", prompt="A younger student asks how to choose electives: easy GPA boosters or harder, practical courses. What do you advise?"),
    # --- Toronto Life ---
    DailyQuestion(id="daily_010", category="Toronto Life", prompt="What was a memorable or frustrating transit ride you had in Toronto recently?"),
    DailyQuestion(id="daily_011", category="Toronto Life", prompt="How does Toronto's weather, like sudden cold snaps or short winter days, change your daily routine?"),
    DailyQuestion(id="daily_012", category="Toronto Life", prompt="A friend from Korea visits Toronto for one free afternoon. What would you plan for them?"),
    DailyQuestion(id="daily_013", category="Toronto Life", prompt="What everyday habit in Canada surprised you at first compared to Korea, and how do you feel about it now?"),
    DailyQuestion(id="daily_014", category="Toronto Life", prompt="How do you handle groceries and quick weekday meals while keeping up with classes?"),
    DailyQuestion(id="daily_015", category="Toronto Life", prompt="Which Toronto neighborhood do you like walking around, and what gives it character?"),
    DailyQuestion(id="daily_016", category="Toronto Life", prompt="Friends are complaining about how expensive Toronto has become. Where do you splurge, and where do you cut back?"),
    DailyQuestion(id="daily_017", category="Toronto Life", prompt="What do you think about tipping prompts at coffee shops and takeout counters in North America?"),
    DailyQuestion(id="daily_018", category="Toronto Life", prompt="When you need a break from screens, how do you like to unwind outdoors around Toronto?"),
    # --- Small Talk & Updates ---
    DailyQuestion(id="daily_019", category="Small Talk & Updates", prompt="Someone asks \"How has your week been?\" What's your answer?"),
    DailyQuestion(id="daily_020", category="Small Talk & Updates", prompt="You run into someone you worked with last semester. What have you been up to lately?"),
    DailyQuestion(id="daily_021", category="Small Talk & Updates", prompt="Someone asks if you've watched or listened to anything good lately. What would you recommend, without spoiling it?"),
    DailyQuestion(id="daily_022", category="Small Talk & Updates", prompt="You sit down for a 15-minute coffee chat with an alumni engineer. How do you introduce yourself and break the ice?"),
    DailyQuestion(id="daily_023", category="Small Talk & Updates", prompt="A classmate asks what you did over the weekend. What did you do?"),
    DailyQuestion(id="daily_024", category="Small Talk & Updates", prompt="What's a random topic or tool you've gotten unexpectedly obsessed with lately?"),
    DailyQuestion(id="daily_025", category="Small Talk & Updates", prompt="Someone complains about 9 AM lectures. What's your sleep schedule, and when do you focus best?"),
    DailyQuestion(id="daily_026", category="Small Talk & Updates", prompt="A friendly barista asks how your day is going and compliments your laptop stickers. How do you keep the chat going?"),
    DailyQuestion(id="daily_027", category="Small Talk & Updates", prompt="Friends are comparing reading week plans. What do you hope to get done, and what will you do just to rest?"),
    # --- Social & Boundaries ---
    DailyQuestion(id="daily_037", category="Social & Boundaries", prompt="A close friend invites you to dinner tonight, but you have a brutal deadline tomorrow. How do you say no warmly?"),
    DailyQuestion(id="daily_038", category="Social & Boundaries", prompt="Your project partner keeps adding extra features two days before the deadline. How do you push back constructively?"),
    DailyQuestion(id="daily_039", category="Social & Boundaries", prompt="Your roommate is being loud late at night. How do you ask them to keep it down without making it awkward?"),
    DailyQuestion(id="daily_040", category="Social & Boundaries", prompt="Halfway through a conversation, you realize you misunderstood the other person's point. How do you recover smoothly?"),
    DailyQuestion(id="daily_041", category="Social & Boundaries", prompt="Someone asks you a tricky question you weren't expecting. How do you buy time, clarify, and then answer clearly?"),
    DailyQuestion(id="daily_042", category="Social & Boundaries", prompt="A classmate asks you to review their slides, but the structure is confusing. How do you give honest feedback without sounding harsh?"),
    DailyQuestion(id="daily_043", category="Social & Boundaries", prompt="In a group meeting, someone asks for an estimate you're not sure about. How do you decline to guess while still sounding reliable?"),
    DailyQuestion(id="daily_044", category="Social & Boundaries", prompt="You're at a gathering and need to leave early to prepare for tomorrow. How do you say goodbye gracefully?"),
    DailyQuestion(id="daily_045", category="Social & Boundaries", prompt="After dinner with friends, everyone ordered very different amounts. How do you bring up splitting the bill fairly?"),
    # --- Requests & Problem Solving ---
    DailyQuestion(id="daily_046", category="Requests & Problem Solving", prompt="Something unexpected came up. How would you ask your TA or instructor for a 24-hour extension?"),
    DailyQuestion(id="daily_047", category="Requests & Problem Solving", prompt="You step away from the counter and realize your takeout order is missing an item. How do you politely ask them to fix it?"),
    DailyQuestion(id="daily_048", category="Requests & Problem Solving", prompt="Your apartment has a heating, leak, or lock problem. How would you describe it over the phone so maintenance knows what to bring?"),
    DailyQuestion(id="daily_049", category="Requests & Problem Solving", prompt="Someone on the phone talks fast, uses slang, and mumbles an address. How do you ask them to repeat it without apologizing five times?"),
    DailyQuestion(id="daily_050", category="Requests & Problem Solving", prompt="You emailed someone about a research opportunity five days ago and heard nothing. How would you follow up politely?"),
    DailyQuestion(id="daily_051", category="Requests & Problem Solving", prompt="Your university account or bank card is locked right before a payment. How do you explain what happened and what you need?"),
    DailyQuestion(id="daily_052", category="Requests & Problem Solving", prompt="It's the evening before a deadline and a teammate still hasn't pushed their part. How do you nudge them clearly and kindly?"),
    DailyQuestion(id="daily_053", category="Requests & Problem Solving", prompt="You bought something that doesn't fit or doesn't match the description. How do you ask for an exchange or refund?"),
    DailyQuestion(id="daily_054", category="Requests & Problem Solving", prompt="Three busy teammates can't agree on a meeting time. What do you propose so everyone can move forward?"),
    # --- Stories & Reflections ---
    DailyQuestion(id="daily_055", category="Stories & Reflections", prompt="What's one daily habit you built, like using Anki, and why did it last when others didn't?"),
    DailyQuestion(id="daily_056", category="Stories & Reflections", prompt="Tell me about a time real numbers made you change your mind."),
    DailyQuestion(id="daily_057", category="Stories & Reflections", prompt="What's a small mistake, like a missed train or a broken script, that permanently changed how you prepare?"),
    DailyQuestion(id="daily_058", category="Stories & Reflections", prompt="What's something you couldn't stand a few years ago but genuinely enjoy today?"),
    DailyQuestion(id="daily_059", category="Stories & Reflections", prompt="Tell me about an interesting conversation you had with someone from a completely different background."),
    DailyQuestion(id="daily_060", category="Stories & Reflections", prompt="What's one challenge of studying abroad in Canada that people don't talk about enough, and how are you dealing with it?"),
    DailyQuestion(id="daily_061", category="Stories & Reflections", prompt="Tell me about a decision you made when you didn't feel ready. How did it turn out?"),
    DailyQuestion(id="daily_062", category="Stories & Reflections", prompt="What's a piece of blunt feedback from a professor, peer, or mentor that actually helped you improve?"),
    DailyQuestion(id="daily_063", category="Stories & Reflections", prompt="After an intense week drains you, what actually restores your energy, and what only wastes your time?"),
    # --- Opinions & Tech ---
    DailyQuestion(id="daily_028", category="Opinions & Tech", prompt="What's your take on smartphone notifications and digital minimalism for students?"),
    DailyQuestion(id="daily_029", category="Opinions & Tech", prompt="For early-career engineers, is working in person still worth the commute? Why or why not?"),
    DailyQuestion(id="daily_030", category="Opinions & Tech", prompt="When you pick up a new technical skill, should you read the fundamentals first or jump straight into building?"),
    DailyQuestion(id="daily_031", category="Opinions & Tech", prompt="How do you think short-form video affects focus and tolerance for boredom?"),
    DailyQuestion(id="daily_032", category="Opinions & Tech", prompt="Why do open-weight AI models matter, even if the strongest models are closed? Explain it in plain language."),
    DailyQuestion(id="daily_033", category="Opinions & Tech", prompt="A friend says algorithm puzzles are outdated because of AI. Do you agree?"),
    DailyQuestion(id="daily_034", category="Opinions & Tech", prompt="For a first full-time job after graduation, which teaches you more: a big company or a small startup? Why?"),
    DailyQuestion(id="daily_035", category="Opinions & Tech", prompt="When does automating your own workflow actually save time, and when is it just productive procrastination?"),
    DailyQuestion(id="daily_036", category="Opinions & Tech", prompt="Do you remember things differently when you read on paper versus a tablet or laptop?"),
    # --- Projects & Presentations ---
    DailyQuestion(id="daily_064", category="Projects & Presentations", prompt="Someone at a hackathon asks what you've built recently. How do you pitch one of your own tools in a few sentences?"),
    DailyQuestion(id="daily_065", category="Projects & Presentations", prompt="What's a design trade-off you had to make, like speed versus accuracy, and how would you explain it to a non-technical person?"),
    DailyQuestion(id="daily_066", category="Projects & Presentations", prompt="What's an experiment or feature you built and later dropped because the results didn't justify it?"),
    DailyQuestion(id="daily_067", category="Projects & Presentations", prompt="Can you summarize your Korean-learner mispronunciation detection project in a minute, including its honest limitation?"),
    DailyQuestion(id="daily_068", category="Projects & Presentations", prompt="How did you track down a bug that worked on your machine but broke in another environment?"),
    DailyQuestion(id="daily_069", category="Projects & Presentations", prompt="How would you open the first 45 seconds of a team presentation to hook the audience without reading slides?"),
    DailyQuestion(id="daily_070", category="Projects & Presentations", prompt="Right after your presentation, someone points out a flaw in your assumptions. How do you respond calmly and credibly?"),
    DailyQuestion(id="daily_071", category="Projects & Presentations", prompt="Why can testing an idea only on historical data fool you? Use an everyday analogy."),
    DailyQuestion(id="daily_072", category="Projects & Presentations", prompt="A mentor asks what technical direction or milestone you're aiming for over the next six months. What's your answer?"),
]

_QUESTION_MAP = {q.id: q for q in DAILY_QUESTIONS}


def get_question_by_id(topic_id: str) -> Optional[DailyQuestion]:
    return _QUESTION_MAP.get(topic_id)
