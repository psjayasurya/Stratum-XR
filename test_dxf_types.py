from collections import Counter
with open('c:\\Users\\TIH06\\Downloads\\GPR\\requirements\\static\\ALLGRIDS.dxf', 'r') as f:
    lines = f.read().splitlines()

types = []
in_entities = False
for i in range(len(lines)):
    line = lines[i].strip()
    if line == 'SECTION':
        if i + 2 < len(lines) and lines[i+2].strip() == 'ENTITIES':
            in_entities = True
    elif line == 'ENDSEC':
        in_entities = False
    
    if in_entities and line == '0':
        types.append(lines[i+1].strip())

print(Counter(types))
