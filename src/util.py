from typing import Union, List, Tuple

def _format_list(li) -> str:
    out = ""
    max_digits = len(str(len(li) - 1))
    for i, l in enumerate(li):
        out += f"{i:0{max_digits}d}: {l}\n"
    return out[:-2]

def _find_in_matched(l: List[Tuple[str]], item:str) -> Tuple[str]:
    for mediaf, jsonf in l:
        if item in mediaf:
            return (mediaf, jsonf)

    return False