with open('scratch/broker_chat_clean.txt', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

idx = text.find('TransitGpsApiController')
if idx != -1:
    section = text[idx+2500:]
    with open('scratch/broker_chat_part2.txt', 'w', encoding='utf-8') as out:
        out.write(section)
    print(f"Saved part 2: {len(section)} characters")
else:
    print("Not found")
