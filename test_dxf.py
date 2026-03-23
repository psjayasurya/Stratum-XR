import re

with open('c:\\Users\\TIH06\\Downloads\\GPR\\requirements\\static\\ALLGRIDS.dxf', 'r') as f:
    lines = f.read().splitlines()

x_vals = []
y_vals = []

for i in range(len(lines)):
    line = lines[i].strip()
    if line == '10':
        val = float(lines[i+1].strip())
        if val != 0.0: x_vals.append(val)
    elif line == '20':
        val = float(lines[i+1].strip())
        if val != 0.0: y_vals.append(val)

if x_vals and y_vals:
    min_x = min(x_vals)
    max_x = max(x_vals)
    min_y = min(y_vals)
    max_y = max(y_vals)
    print(f'Entities parsed: {len(x_vals)}')
    print(f'Bounds X (Lon): {min_x} to {max_x}')
    print(f'Bounds Y (Lat): {min_y} to {max_y}')
    print(f'Width: {max_x - min_x}')
    print(f'Height: {max_y - min_y}')
else:
    print('No coordinates found')
