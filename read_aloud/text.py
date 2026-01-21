from word_level_matcher import _get_words_timestamps,_is_punctuation,_normalize_token,_get_char_timestamps
from word_level_matcher import PAUSE_PUNCTUATION,PAUSE_THRESHOLDS


words_json =_get_words_timestamps()
char_json = _get_char_timestamps()
# # print(words)
# words = [word['value'] for word in words_json]
# print("============================")
# for word in words:
#     print(f"{word}->{_is_punctuation(word)}")
# print("============================")

# print(char_json)

chars = [char['value'][0] for char in char_json]
# print(chars)
for char in chars:
    if _is_punctuation(char):
        print(f"{char} -> {_is_punctuation(char)}")
print("============================")
