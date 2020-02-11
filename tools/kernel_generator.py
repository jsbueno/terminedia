import sys

from terminedia import V2, shape

template = """{{
{},
    "default": " ",
}}
"""
value_template = """\
    "{}"\\
    "{}"\\
    "{}": " "
"""


def main():
    values = []
    total = int(sys.argv[1]) if len(sys.argv) > 1  else 512
    include_empties = len(sys.argv) > 3


    for i in range(total):
        new = shape((3,3))
        if i & 1 :
            new[1,1] = "#"
        elif not include_empties:
            continue
        if i & 0b10:
            new[1,0] = "#"
        if i & 0b100:
            new[0, 1] = "#"
        if i & 0b1000:
            new[2, 1] = "#"
        if i & 0b10000:
            new[1, 2] = "#"
        if i & 0b100000:
            new[0, 0] = "#"
        if i & 0b1000000:
            new[2, 0] = "#"
        if i & 0b10000000:
            new[0, 2] = "#"
        if i & 0b100000000:
            new[2, 2] = "#"

        values.append(value_template.format(
            *["".join(new.value_data[i: i+3]) for i in range(0, 9, 3)]
        ))

    return template.format(",\n".join(values))


if __name__ == "__main__":
    kernel = main()
    print(kernel)
