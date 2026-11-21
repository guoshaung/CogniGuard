"""Four isolated synthetic grading controls, kept out of all corpus results."""
from data_cases import RUN, dump
from experiment import offline_judge

CONTROLS = [
    ("A rectangle is 7 by 4. Find its area.", "I added 7 and 4 and got 11.",
     "Area uses multiplication of the side lengths.", "Adding the sides gives the area of 11.",
     "Ask how many unit squares fit in one row and how many rows there are.",
     "Tell the student that area and perimeter are both found by addition."),
    ("Solve 3x + 4 = 19.", "I moved 4 and wrote 3x = 23.",
     "The same quantity must be subtracted from both sides.", "Adding four to the right balances the equation.",
     "What happens to both sides when you subtract four?",
     "Keep 23 and say the student has already solved the equation."),
    ("Which is larger, 3/5 or 3/8?", "3/8 because eight is bigger.",
     "With equal numerators, compare the sizes of the pieces.", "The larger denominator always makes a fraction larger.",
     "Draw equal wholes and compare three fifth-sized pieces with three eighth-sized pieces.",
     "Use the denominator alone to confirm the answer."),
    ("Find the speed if you travel 90 kilometers in 3 hours.", "I got 270 kilometers per hour.",
     "The student multiplied instead of finding distance per hour.", "Multiplication produces the correct per-hour rate.",
     "How far would you travel in one of three equal one-hour periods?",
     "Multiply the 270 by another 3 to convert to per-hour."),
]


def main():
    controls = []
    for index, (problem, current, good, bad, good_hint, bad_hint) in enumerate(CONTROLS, 1):
        case = {"case": f"synthetic-grader-control-{index}", "source": "SYNTHETIC_CONTROL",
                "task_family": "none", "topic": "short math", "problem": problem,
                "current": current, "candidates": []}
        trace = {"rows": {name: {"teacher": {"output": {"diagnosis": diag, "hint": hint}}}
                          for name, diag, hint in [("known_good", good, good_hint), ("known_bad", bad, bad_hint)]}}
        result = offline_judge(case, trace, {})
        ok = result["scores"]["known_good"][0]
        wrong = result["scores"]["known_bad"][0]
        controls.append({"case": case["case"], "correctness_discriminated": ok is not None and wrong is not None and ok > wrong, **result})
    dump(RUN / "grader_controls.json", controls)
    print("Scoring controls passed:", sum(c["correctness_discriminated"] for c in controls), "/", len(controls))


if __name__ == "__main__":
    main()
