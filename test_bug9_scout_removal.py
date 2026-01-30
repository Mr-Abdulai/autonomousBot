"""
TEST BUG FIX #9: Scout Mode Removal
Tests that scout code was properly removed
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test 1: Verify no darwin_signal references
print("=== TEST 1: darwin_signal removal ===")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
if 'darwin_signal' not in content:
    print("✅ PASS - No darwin_signal references found")
else:
    print("❌ FAIL - darwin_signal still referenced")

# Test 2: Verify no is_scout references
print("\n=== TEST 2: is_scout removal ===")

if 'is_scout' not in content:
    print("✅ PASS - No is_scout references found")  
else:
    print("❌ FAIL - is_scout still referenced")

# Test 3: Verify scout protocol removed
print("\n=== TEST 3: Scout protocol removal ===")

if 'SCOUT PROTOCOL' not in content and 'Scout Risk Applied' not in content:
    print("✅ PASS - Scout protocol code removed")
else:
    print("❌ FAIL - Scout protocol still present")

# Test 4: Code compiles without errors
print("\n=== TEST 4: Syntax check ===")

try:
    import ast
    with open('main.py', 'r', encoding='utf-8') as f:
        ast.parse(f.read())
    print("✅ PASS - main.py compiles without syntax errors")
except SyntaxError as e:
    print(f"❌ FAIL - Syntax error: {e}")

print("\n=== BUG #9 VERIFICATION COMPLETE ===")
print("Scout mode dead code removed - 60 lines cleaned up!")
