"""Curated speaking topic bank (Campus/Daily, Tech Interview, IELTS/TOEFL) and rapid warmups."""
from __future__ import annotations

import random
from typing import Iterable, List, Optional, Sequence

from speaking.models import Topic, TrackName

WARMUP_PROMPTS: List[str] = [
    "What did you do right before starting this speaking session?",
    "Describe the weather in Toronto today and how it affects your mood.",
    "What is one small thing that annoyed or pleased you today?",
    "What did you eat for your last meal, and would you recommend it?",
    "If you had an extra free hour right now, how would you spend it?",
    "Which course or project is taking most of your mental energy this week?",
    "What is a place near campus you go to often, and why?",
    "Tell me about a song, video, or article you came across recently.",
    "Are you more productive in the morning or late at night? Give a quick example.",
    "What is one habit you are trying to keep or break this month?",
    "If a friend visited Toronto for just one afternoon, where would you take them?",
    "What is a tool or app on your phone you could not live without?",
    "Describe your desk or study setup right now in three sentences.",
    "What is something you used to dislike but now enjoy?",
    "How do you usually recharge after an intense exam or deadline?",
    "Tell me one plan you have for this coming weekend.",
]

TOPICS: List[Topic] = [
    # --- Track 1: Daily / Campus (Toronto life, classes, presentations, small talk) ---
    Topic(
        id="daily_01",
        track="daily",
        title="Explaining your major to a non-engineer",
        prompt="A student from another faculty asks what you study and why you chose it. Explain it clearly without heavy jargon.",
        bullets=["What your major focuses on", "One concrete project you worked on", "Why it interests you"],
    ),
    Topic(
        id="daily_02",
        track="daily",
        title="Office hours question",
        prompt="You are visiting a professor during office hours because you are stuck on a concept or assignment. Explain what you tried and where you are confused.",
        bullets=["Context of the problem", "What you already attempted", "Specific question you want clarified"],
    ),
    Topic(
        id="daily_03",
        track="daily",
        title="Group project disagreement",
        prompt="A teammate wants to take a shortcut on a group project that you think will hurt the final grade. Voice your concern politely and propose an alternative.",
        bullets=["Acknowledge their constraint", "Explain the technical or grade risk", "Propose a realistic compromise"],
    ),
    Topic(
        id="daily_04",
        track="daily",
        title="Living in Toronto vs Korea",
        prompt="Compare one everyday aspect of living in Toronto with Korea (transit, food, social culture, or university life).",
        bullets=["Specific difference you noticed", "One surprising advantage", "One thing you still miss"],
    ),
    Topic(
        id="daily_05",
        track="daily",
        title="Pitching a side project at a mixer",
        prompt="You are at a campus tech mixer and someone asks what you have been building recently. Give a 90-second natural pitch.",
        bullets=["Problem you wanted to solve", "How your system works", "One real obstacle you ran into"],
    ),
    Topic(
        id="daily_06",
        track="daily",
        title="Turning down a plan gracefully",
        prompt="A friend invites you to hang out before a major deadline. Decline warmly without sounding cold, and suggest another time.",
        bullets=["Show appreciation", "Explain your constraint concisely", "Offer a concrete alternative"],
    ),
    Topic(
        id="daily_07",
        track="daily",
        title="Classroom discussion contribution",
        prompt="In a seminar, the professor asks whether AI coding assistants help or hurt undergrads learning fundamentals. Share a balanced opinion.",
        bullets=["Clear stance", "Personal example from coursework", "Condition where your view changes"],
    ),
    Topic(
        id="daily_08",
        track="daily",
        title="Summarizing a tough week",
        prompt="A classmate asks 'How has your week been?' Give an engaging, natural 90-second update instead of just saying 'busy'.",
        bullets=["Main highlight or stressor", "How you handled it", "What you are looking forward to"],
    ),
    # --- Track 2: Tech / Internship Interview (STAR Behavioral & Technical Communication) ---
    Topic(
        id="int_01",
        track="interview",
        title="Tell me about yourself (SWE / ML Intern)",
        prompt="Walk me through your background and why you are interested in this engineering internship.",
        bullets=["Current focus & technical strengths", "1-2 standout projects with measurable results", "What you want to contribute"],
    ),
    Topic(
        id="int_02",
        track="interview",
        title="Hardest bug you debugged",
        prompt="Tell me about a particularly stubborn bug or system failure you diagnosed and fixed.",
        bullets=["Situation & symptom", "How you isolated the root cause", "Fix & how you prevented recurrence"],
    ),
    Topic(
        id="int_03",
        track="interview",
        title="Technical trade-off decision",
        prompt="Describe a time you had to choose between two technical approaches under a constraint (latency, memory, accuracy, or deadline).",
        bullets=["Options considered", "Metrics or evidence used", "Trade-off accepted and outcome"],
    ),
    Topic(
        id="int_04",
        track="interview",
        title="Failed experiment or mistake",
        prompt="Tell me about a project or experiment that did not work as expected. What did you learn?",
        bullets=["What you tried and expected", "Why it failed (data/architecture/assumption)", "Concrete change you made afterward"],
    ),
    Topic(
        id="int_05",
        track="interview",
        title="Learning a new stack quickly",
        prompt="Give an example of when you had to pick up an unfamiliar framework, domain, or codebase quickly to deliver results.",
        bullets=["Why the ramp-up was urgent", "How you structured your learning", "What you shipped"],
    ),
    Topic(
        id="int_06",
        track="interview",
        title="Working with a difficult or misaligned teammate",
        prompt="Describe a time you disagreed with a teammate on direction or priorities. How did you resolve it?",
        bullets=["Nature of the disagreement", "How you communicated and listened", "Final resolution and result"],
    ),
    Topic(
        id="int_07",
        track="interview",
        title="Explaining an ML or quant project end-to-end",
        prompt="Pick one of your projects (e.g., mispronunciation detection, quant validator, or Anki automation) and explain the architecture and evaluation.",
        bullets=["Problem & baseline", "Key design choice", "Quantitative result and limitation"],
    ),
    Topic(
        id="int_08",
        track="interview",
        title="Handling tight deadlines & prioritization",
        prompt="Tell me about a time you had multiple urgent deliverables at once. How did you decide what to cut or prioritize?",
        bullets=["Competing priorities", "Decision framework", "Outcome and reflection"],
    ),
    # --- Track 3: IELTS / TOEFL Speaking (Part 2 Monologue + Part 3 Extension) ---
    Topic(
        id="ielts_01",
        track="ielts",
        title="A skill that took a long time to learn",
        prompt="Describe a useful skill you spent a long time developing. Explain how you practiced it, what was difficult, and how it helps you now.",
        bullets=["What the skill is", "Specific obstacles you faced", "How it changed your daily life"],
    ),
    Topic(
        id="ielts_02",
        track="ielts",
        title="A technology that changed how you work",
        prompt="Describe a piece of technology or software that significantly changed how you study or work.",
        bullets=["What it does", "How you did things before", "One drawback of relying on it"],
    ),
    Topic(
        id="ielts_03",
        track="ielts",
        title="A difficult decision with long-term impact",
        prompt="Describe an important decision you made that was not easy at the time.",
        bullets=["What options you had", "Why it felt risky", "How you view the decision today"],
    ),
    Topic(
        id="ielts_04",
        track="ielts",
        title="An interesting conversation with someone different",
        prompt="Describe a memorable conversation you had with someone from a very different background or field.",
        bullets=["Where and how it happened", "What you talked about", "Why it stayed with you"],
    ),
    Topic(
        id="ielts_05",
        track="ielts",
        title="A crowded or quiet place you remember",
        prompt="Describe a place where you feel focused or inspired to think clearly.",
        bullets=["Where it is and what it looks like", "When you go there", "Why it works better than other places"],
    ),
    Topic(
        id="ielts_06",
        track="ielts",
        title="Should universities prioritize practical skills over theory?",
        prompt="TOEFL/IELTS Opinion: Some argue universities should focus mainly on job-ready skills rather than abstract theory. Do you agree or disagree?",
        bullets=["Clear position", "Two concrete reasons or examples", "Brief counter-argument and rebuttal"],
    ),
    Topic(
        id="ielts_07",
        track="ielts",
        title="Remote work vs in-person collaboration",
        prompt="Compare working remotely with working in an office for early-career engineers. Which is better overall and why?",
        bullets=["Key benefit of each", "Specific risk for junior workers", "Your overall recommendation"],
    ),
    Topic(
        id="ielts_08",
        track="ielts",
        title="A time you changed your mind based on evidence",
        prompt="Describe a belief or habit you used to hold strongly, until data or experience convinced you otherwise.",
        bullets=["Your original view", "What challenged it", "How your behavior changed"],
    ),
]

TRACK_ORDER: Sequence[TrackName] = ("daily", "interview", "ielts")


def get_topic_by_id(topic_id: str) -> Optional[Topic]:
    for topic in TOPICS:
        if topic.id == topic_id:
            return topic
    return None


def pick_warmups(count: int = 2, rng: Optional[random.Random] = None) -> List[str]:
    r = rng or random
    k = min(count, len(WARMUP_PROMPTS))
    return r.sample(WARMUP_PROMPTS, k)


def select_topic(
    track: Optional[TrackName],
    due_topic_ids: Iterable[str],
    recent_topic_ids: Iterable[str],
    last_track: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> Topic:
    """SRS 만기 주제를 최우선으로 선택하고, 없으면 직전 트랙과 다른 트랙에서 최근 미사용 주제를 고른다."""
    r = rng or random
    due_set = set(due_topic_ids)
    recent_set = set(recent_topic_ids)

    # 1. 지정 트랙 우선 (또는 직전 트랙 다음 순환)
    chosen_track: TrackName
    if track in TRACK_ORDER:
        chosen_track = track  # type: ignore[assignment]
    elif last_track in TRACK_ORDER:
        idx = TRACK_ORDER.index(last_track)  # type: ignore[arg-type]
        chosen_track = TRACK_ORDER[(idx + 1) % len(TRACK_ORDER)]
    else:
        chosen_track = TRACK_ORDER[0]

    # 2. 지정/전체 SRS 만기 주제 우선 재출제
    due_in_track = [t for t in TOPICS if t.id in due_set and (track is None or t.track == chosen_track)]
    if due_in_track:
        return r.choice(due_in_track)

    # 3. 선택 트랙 내 최근 미사용 주제
    candidates = [t for t in TOPICS if t.track == chosen_track and t.id not in recent_set]
    if not candidates:
        candidates = [t for t in TOPICS if t.track == chosen_track]
    return r.choice(candidates)
