with open('c:\\Users\\TIH06\\Downloads\\GPR\\requirements\\static\\ALLGRIDS.dxf', 'r') as f:
    lines = f.read().splitlines()

in_entities = False
x_vals = []
y_vals = []

for i in range(len(lines)):
    line = lines[i].strip()
    if line == 'SECTION':
        if lines[i+2].strip() == 'ENTITIES':
            in_entities = True
    elif line == 'ENDSEC':
        in_entities = False
        
    if in_entities:
        if line == '10':
            x_vals.append(float(lines[i+1].strip()))
        elif line == '20':
            y_vals.append(float(lines[i+1].strip()))

if x_vals and y_vals:
    print(f'Vertices parsed: {len(x_vals)}')
    print(f'Bounds X: {min(x_vals)} to {max(x_vals)}')
    print(f'Bounds Y: {min(y_vals)} to {max(y_vals)}')
else:
    print('No coordinates found in ENTITIES section')
