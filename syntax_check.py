#!/usr/bin/env python3
# Syntax check for ProcessDamage implementation
import ast
import sys
import os

def check_syntax(file_path):
    """Check if a Python file has valid syntax"""
    try:
        with open(file_path, 'r') as f:
            source = f.read()
        
        # Parse the source code
        ast.parse(source)
        print(f"✅ {file_path} has valid syntax")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking {file_path}: {e}")
        return False

def main():
    """Check syntax of all relevant files"""
    print("Checking syntax of ProcessDamage implementation...")
    print("=" * 50)
    
    files_to_check = [
        "actions/process_damage.py",
        "action_registry.py",
        "tests/test_process_damage.py"
    ]
    
    all_good = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            all_good &= check_syntax(file_path)
        else:
            print(f"❌ File not found: {file_path}")
            all_good = False
    
    print("=" * 50)
    if all_good:
        print("✅ All files have valid syntax!")
    else:
        print("❌ Some files have syntax errors!")
    
    return all_good

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)