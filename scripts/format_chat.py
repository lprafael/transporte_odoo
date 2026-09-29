# -*- coding: utf-8 -*-
with open('scratch/clean_text.txt', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Split by "Has dicho"
parts = re.split(r'Has dicho\s*', text)
print(f"Total conversation turns: {len(parts)}")

with open('scratch/formatted_turns.txt', 'w', encoding='utf-8') as out:
    for i, p in enumerate(parts):
        out.write(f"\n{'='*70}\nTURN {i}\n{'='*70}\n")
        out.write(p[:4000]) # First 4000 chars of each turn
        out.write("\n\n")

print("Saved scratch/formatted_turns.txt")
