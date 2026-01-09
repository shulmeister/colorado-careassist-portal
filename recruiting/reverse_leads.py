#!/usr/bin/env python3
"""Reverse the order of leads data"""

# Read the current import file
with open('import_leads.py', 'r') as f:
    content = f.read()

# Find the leads_data section
start_marker = 'leads_data = ['
end_marker = ']'

start_idx = content.find(start_marker)
if start_idx == -1:
    print("Could not find leads_data section")
    exit(1)

# Find the end of the leads_data list
bracket_count = 0
end_idx = start_idx + len(start_marker)
for i, char in enumerate(content[start_idx + len(start_marker):]):
    if char == '[':
        bracket_count += 1
    elif char == ']':
        if bracket_count == 0:
            end_idx = start_idx + len(start_marker) + i
            break
        bracket_count -= 1

# Extract the leads data
leads_section = content[start_idx:end_idx + 1]

# Parse the leads (simple approach - split by lines and reverse)
lines = leads_section.split('\n')
header_line = lines[0]  # "leads_data = ["
footer_line = lines[-1]  # "]"
data_lines = lines[1:-1]

# Reverse the data lines
reversed_lines = [header_line] + data_lines[::-1] + [footer_line]
reversed_section = '\n'.join(reversed_lines)

# Replace in content
new_content = content[:start_idx] + reversed_section + content[end_idx + 1:]

# Write back
with open('import_leads.py', 'w') as f:
    f.write(new_content)

print("Successfully reversed the order of leads data!")



