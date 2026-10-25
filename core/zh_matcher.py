"""중국어 단어가 문장에 '단어로' 들어 있는지 판정한다.

중국어는 띄어쓰기가 없어 글자 포함만 보면 '好'가 好吃·好久·好像에 붙는다.
jieba로 문장을 단어 단위로 자르고, 등록 단어를 사전에 넣어 그 단어가 한 덩어리로 잘리게 한다.
- 한 글자 단어: 잘린 단어와 정확히 같을 때만
- 두 글자 이상: 잘린 단어와 같거나, 연속된 단어를 이은 것과 같거나(一个/星期), 잘린 단어 안에 있을 때(今天天气)
"""
import logging
from typing import Iterable, List

import jieba

jieba.setLogLevel(logging.WARNING)

# 너무 흔해서 연결 의미가 없는 한 글자
STOP_1CHAR = set("的了我你他在是有就不吗吧呢很")


class ChineseMatcher:
    def __init__(self, vocab_words: Iterable[str]):
        self._tokenizer = jieba.Tokenizer()
        for w in set(vocab_words):
            if len(w) >= 2:
                self._tokenizer.add_word(w, freq=100000)

    def tokens(self, sentence: str) -> List[str]:
        return [t for t in self._tokenizer.lcut(sentence, HMM=False) if t.strip()]

    @staticmethod
    def contains(word: str, tokens: List[str]) -> bool:
        if not word or (len(word) == 1 and word in STOP_1CHAR):
            return False
        if word in tokens:
            return True
        if len(word) == 1:
            return False
        if any(word in t for t in tokens):
            return True
        for i in range(len(tokens)):
            joined = tokens[i]
            for j in range(i + 1, len(tokens)):
                joined += tokens[j]
                if joined == word:
                    return True
                if len(joined) >= len(word):
                    break
        return False
