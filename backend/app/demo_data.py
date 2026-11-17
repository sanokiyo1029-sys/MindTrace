"""Built-in demo data used ONLY when tests/fixtures/ (owned by Samrudh) doesn't have the file yet.

Once Samrudh's fixtures land, the backend reads those instead (see app/ai_bridge.py and app/seed.py).
All student names are fictional.
"""

ROSTER = [
    {"id": "st_01", "display_name": "Aarav", "student_code": "7A-01", "pin": "1111"},
    {"id": "st_02", "display_name": "Diya", "student_code": "7A-02", "pin": "2222"},
    {"id": "st_03", "display_name": "Kabir", "student_code": "7A-03", "pin": "3333"},
    {"id": "st_04", "display_name": "Meera", "student_code": "7A-04", "pin": "4444"},
    {"id": "st_05", "display_name": "Rehan", "student_code": "7A-05", "pin": "5555"},
]


def _act(title, steps):
    return {"title": title, "minutes": 5, "steps": steps}


MISCONCEPTIONS = [
    {
        "id": "M_ADD_DENOMS", "topic": "fractions",
        "label": "Adds the denominators as well as the numerators",
        "student_friendly": "You may have added the bottom numbers too. The bottom number tells the size of each piece, and that stays the same when the pieces are the same size.",
        "teaching_activity": _act("Fraction strips: same-size pieces", [
            "Show 1/3 + 1/3 with two paper strips cut into thirds.",
            "Ask: did the pieces get smaller when we joined them?",
            "Write 2/3 and compare it with 2/6 on a strip cut into sixths.",
        ]),
    },
    {
        "id": "M_MULTIPLY_INSTEAD", "topic": "fractions",
        "label": "Multiplies the fractions instead of adding them",
        "student_friendly": "You may have multiplied instead of added. Adding joins the pieces together, so the answer should be bigger than each part.",
        "teaching_activity": _act("Add means join: number-line hops", [
            "Draw a 0 to 1 number line split into equal parts.",
            "Hop the first fraction, then hop the second from where you landed.",
            "Ask: is the answer bigger or smaller than where we started?",
        ]),
    },
    {
        "id": "M_IGNORE_SECOND", "topic": "fractions",
        "label": "Ignores the second fraction",
        "student_friendly": "You may have only counted the first fraction. Shade both parts on one bar and count all the shaded pieces.",
        "teaching_activity": _act("Shade both on one bar", [
            "Draw one bar split into equal parts.",
            "Shade the first fraction in one colour and the second in another.",
            "Count every shaded piece together.",
        ]),
    },
    {
        "id": "M_NO_COMMON_DENOM", "topic": "fractions",
        "label": "Adds unlike fractions without making a common denominator",
        "student_friendly": "You may have added tops and bottoms straight away. Halves and thirds are different-sized pieces, so first change them into same-sized pieces.",
        "teaching_activity": _act("Fold into same-size pieces", [
            "Fold one paper into halves and another into thirds.",
            "Refold both into sixths and count the pieces again.",
            "Add the sixths: 3/6 + 2/6 = 5/6.",
        ]),
    },
    {
        "id": "M_LCM_ERROR", "topic": "fractions",
        "label": "Finds a common denominator but does not scale the numerators",
        "student_friendly": "You found the right bottom number, but the top number must grow by the same amount. 1/2 becomes 3/6, not 1/6.",
        "teaching_activity": _act("Equivalent fraction wall", [
            "Show a fraction wall with halves, thirds and sixths.",
            "Point out that 1/2 lines up with 3/6, not 1/6.",
            "Practise: multiply top and bottom by the same number.",
        ]),
    },
    {
        "id": "M_WHOLE_NUMBER_BIAS", "topic": "fractions",
        "label": "Thinks a fraction with bigger numbers is bigger",
        "student_friendly": "You may have picked the fraction with bigger numbers. A fraction is a size, so compare how much of the whole each one covers.",
        "teaching_activity": _act("Place them on a number line", [
            "Draw 0 to 1 and mark 1/2.",
            "Place each fraction and compare its distance from 1.",
            "Ask: which covers more of the whole?",
        ]),
    },
    {
        "id": "M_GAP_THINKING", "topic": "fractions",
        "label": "Compares fractions by the gap between top and bottom",
        "student_friendly": "You may have looked at how far the top is from the bottom. 1/2 and 9/10 both miss one piece, but the pieces are very different sizes.",
        "teaching_activity": _act("Same gap, different size", [
            "Show 1/2 and 9/10 as bars: both are missing one piece.",
            "Ask: is the missing piece the same size?",
            "Compare using a common denominator.",
        ]),
    },
    {
        "id": "M_CANT_COMPARE_UNLIKE", "topic": "fractions",
        "label": "Believes fractions with different denominators can't be compared",
        "student_friendly": "Fractions with different bottom numbers can be compared: change them to the same bottom number, or compare each to 1/2.",
        "teaching_activity": _act("Benchmark against 1/2", [
            "Ask: is each fraction more or less than one half?",
            "If both are on the same side, use a common denominator.",
            "Check with a drawing.",
        ]),
    },
    {
        "id": "M_SMALLER_DENOM_BIGGER", "topic": "fractions",
        "label": "Compares only denominators: thinks a smaller denominator always means a bigger fraction",
        "student_friendly": "A smaller bottom number means bigger pieces, but you also need to count how many pieces. Look at the top number too.",
        "teaching_activity": _act("Size of piece AND number of pieces", [
            "Show 3/5 and 5/7 as bars.",
            "Fifths are bigger pieces, but 5/7 has more of them.",
            "Compare with a common denominator: 21/35 vs 25/35.",
        ]),
    },
]


def _q(concept, stem, options, answer, explanation, distractors, difficulty="easy"):
    return {
        "topic": "fractions", "concept": concept, "stem": stem, "options": options,
        "answer": answer, "explanation": explanation,
        "distractors": {k: {"misconception_id": m, "why": w} for k, (m, w) in distractors.items()},
        "difficulty": difficulty, "source": "sample",
    }


QUESTIONS = [
    _q("adding fractions with equal denominators", "What is 1/3 + 1/3?",
       {"A": "2/6", "B": "2/3", "C": "1/9", "D": "1/3"}, "B",
       "Same denominator: add the numerators, keep the denominator. 1/3 + 1/3 = 2/3.",
       {"A": ("M_ADD_DENOMS", "Added top and bottom numbers"),
        "C": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions"),
        "D": ("M_IGNORE_SECOND", "Ignored the second fraction")}),
    _q("adding fractions with unequal denominators (LCM)", "What is 1/2 + 1/3?",
       {"A": "2/5", "B": "5/6", "C": "2/6", "D": "1/6"}, "B",
       "Make sixths: 1/2 = 3/6 and 1/3 = 2/6, so 3/6 + 2/6 = 5/6.",
       {"A": ("M_NO_COMMON_DENOM", "Added tops and bottoms without a common denominator"),
        "C": ("M_LCM_ERROR", "Used 6 as the denominator but did not scale the numerators"),
        "D": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions")}, "medium"),
    _q("comparing fractions", "Which is greater: 2/3 or 3/5?",
       {"A": "3/5", "B": "2/3", "C": "They are equal", "D": "Can't compare: different denominators"}, "B",
       "Use fifteenths: 2/3 = 10/15 and 3/5 = 9/15, so 2/3 is greater.",
       {"A": ("M_WHOLE_NUMBER_BIAS", "Picked the fraction with bigger numbers"),
        "C": ("M_GAP_THINKING", "Both are missing one piece, so thought they are equal"),
        "D": ("M_CANT_COMPARE_UNLIKE", "Thought unlike fractions can't be compared")}, "medium"),
    _q("adding fractions with equal denominators", "What is 3/8 + 2/8?",
       {"A": "5/16", "B": "5/8", "C": "6/64", "D": "3/8"}, "B",
       "Same denominator: 3 eighths + 2 eighths = 5 eighths.",
       {"A": ("M_ADD_DENOMS", "Added top and bottom numbers"),
        "C": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions"),
        "D": ("M_IGNORE_SECOND", "Ignored the second fraction")}),
    _q("adding fractions with unequal denominators (LCM)", "What is 2/3 + 1/6?",
       {"A": "3/9", "B": "5/6", "C": "3/6", "D": "2/18"}, "B",
       "2/3 = 4/6, so 4/6 + 1/6 = 5/6.",
       {"A": ("M_NO_COMMON_DENOM", "Added tops and bottoms without a common denominator"),
        "C": ("M_LCM_ERROR", "Used 6 but did not scale 2/3 to 4/6"),
        "D": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions")}, "medium"),
]

# Transfer questions with NEW numbers, keyed by the misconception they re-check.
FOLLOWUPS = {
    "M_ADD_DENOMS": _q("adding fractions with equal denominators", "What is 2/5 + 1/5?",
                       {"A": "3/10", "B": "3/5", "C": "2/25", "D": "2/5"}, "B",
                       "Same-size pieces: 2 fifths + 1 fifth = 3 fifths.",
                       {"A": ("M_ADD_DENOMS", "Added top and bottom numbers"),
                        "C": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions"),
                        "D": ("M_IGNORE_SECOND", "Ignored the second fraction")}),
    "M_NO_COMMON_DENOM": _q("adding fractions with unequal denominators (LCM)", "What is 1/4 + 1/2?",
                            {"A": "2/6", "B": "3/4", "C": "2/4", "D": "1/8"}, "B",
                            "1/2 = 2/4, so 1/4 + 2/4 = 3/4.",
                            {"A": ("M_NO_COMMON_DENOM", "Added tops and bottoms"),
                             "C": ("M_LCM_ERROR", "Used 4 but did not scale 1/2 to 2/4"),
                             "D": ("M_MULTIPLY_INSTEAD", "Multiplied the fractions")}, "medium"),
    "M_WHOLE_NUMBER_BIAS": _q("comparing fractions", "Which is greater: 3/5 or 5/7?",
                              {"A": "3/5", "B": "5/7", "C": "They are equal", "D": "Can't compare: different denominators"}, "B",
                              "Use 35ths: 3/5 = 21/35 and 5/7 = 25/35, so 5/7 is greater.",
                              {"A": ("M_SMALLER_DENOM_BIGGER", "Looked only at the denominators"),
                               "C": ("M_GAP_THINKING", "Both are missing two pieces, so thought they are equal"),
                               "D": ("M_CANT_COMPARE_UNLIKE", "Thought unlike fractions can't be compared")}, "medium"),
}
FOLLOWUPS["M_MULTIPLY_INSTEAD"] = FOLLOWUPS["M_ADD_DENOMS"]
FOLLOWUPS["M_IGNORE_SECOND"] = FOLLOWUPS["M_ADD_DENOMS"]
FOLLOWUPS["M_LCM_ERROR"] = FOLLOWUPS["M_NO_COMMON_DENOM"]
FOLLOWUPS["M_GAP_THINKING"] = FOLLOWUPS["M_WHOLE_NUMBER_BIAS"]
FOLLOWUPS["M_CANT_COMPARE_UNLIKE"] = FOLLOWUPS["M_WHOLE_NUMBER_BIAS"]
FOLLOWUPS["M_SMALLER_DENOM_BIGGER"] = FOLLOWUPS["M_WHOLE_NUMBER_BIAS"]
