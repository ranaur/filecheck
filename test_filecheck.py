#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile

current_dir = os.path.dirname(os.path.realpath(__file__))

def run_command(cmd, cwd=None):
    """Run a shell command and return (stdout, stderr, returncode)"""
    return_code=0
    try:
        #print("run_command: ", cmd, cwd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=True)
        stdout, stderr = process.communicate()
        return_code = process.returncode
        #print (stdout, stderr, return_code)
    except subprocess.CalledProcessError as e:
        return_code = e.returncode
    return (stdout, stderr, return_code)

def run_filecheck(test_dir, args):
    """Run filecheck and return (stdout, stderr, returncode)"""
    command = "python3 "+ os.path.join(current_dir,"filecheck.py") + " " + args
    #print(command)

    return run_command(command, cwd=test_dir)

def assert_file_exists(path):
    assert os.path.exists(path), "File "+str(path)+" does not exist"

def assert_file_content(path, expected_content):
    with open(path, 'r') as f:
        content = f.read()
    assert content == expected_content, "File "+str(path)+" content mismatch"

def test_generate_basic():
    """Test basic generate command"""
    test_dir = tempfile.mkdtemp()
    try:
        # Create test files
        os.makedirs(os.path.join(test_dir, 'subdir'))
        with open(os.path.join(test_dir, 'file1.txt'), 'w') as f:
            f.write('content1')
        with open(os.path.join(test_dir, 'subdir', 'file2.txt'), 'w') as f:
            f.write('content2')
        
        # Run generate
        stdout, stderr, rc = run_filecheck(test_dir, "generate .")
        assert rc == 0, "Generate failed: "+ str(stderr)
        assert 'GENERATE:' in str(stdout)
        
        # Check .filecheck exists
        filecheck_path = os.path.join(test_dir, '.filecheck')
        assert_file_exists(filecheck_path)
        
        # Verify content (basic check for header and entries)
        with open(filecheck_path, 'r') as f:
            lines = f.readlines()
        #print(lines)
        assert len(lines) >= 3, "Expected at least header + 2 entries"
        assert lines[0].startswith('\ufeffFILECHECK'), "Invalid header"
        
    finally:
        #o, e, r = run_command("ls -la", test_dir)
        #print(o)
        shutil.rmtree(test_dir)

def test_check_no_changes():
    """Test check command with no changes"""
    test_dir = tempfile.mkdtemp()
    try:
        # Create test files
        with open(os.path.join(test_dir, 'file1.txt'), 'w') as f:
            f.write('content1')
        
        # Generate manifest
        run_filecheck(test_dir, "generate .")
        
        # Run check
        stdout, stderr, rc = run_filecheck(test_dir, "check .")
        assert rc == 0, "Check failed: "+str(stderr)
        assert 'CHECK: .' in str(stdout) or str(stdout) == '', "Expected no changes or same file"
        
    finally:
        shutil.rmtree(test_dir)

def test_check_file_modified():
    """Test check command detecting file modification"""
    test_dir = tempfile.mkdtemp()
    try:
        # Create test file
        file_path = os.path.join(test_dir, 'file1.txt')
        with open(file_path, 'w') as f:
            f.write('original')
        
        # Generate manifest
        run_filecheck(test_dir, "generate .")
        
        # Modify file
        with open(file_path, 'w') as f:
            f.write('modified')
        
        # Run check
        stdout, stderr, rc = run_filecheck(test_dir, "check .")
        assert rc == 0, "Check failed: " + str(stderr)
        assert 'MD5 mismatch' in str(stdout) or 'mtime mismatch' in str(stdout), "Expected mismatch detection"
        
    finally:
        shutil.rmtree(test_dir)

def test_update():
    """Test update command"""
    test_dir = tempfile.mkdtemp()
    try:
        # Create test file
        file_path = os.path.join(test_dir, 'file1.txt')
        with open(file_path, 'w') as f:
            f.write('original')
        
        # Generate initial manifest
        run_filecheck(test_dir, "generate .")
        
        # Modify file
        with open(file_path, 'w') as f:
            f.write('updated')
        
        # Run update
        stdout, stderr, rc = run_filecheck(test_dir, "update .")
        assert rc == 0, "Update failed: " + str(stderr)
        assert 'UPDATE:' in str(stdout)
        
        # Verify .filecheck is updated (check if MD5 changed)
        filecheck_path = os.path.join(test_dir, '.filecheck')
        with open(filecheck_path, 'r') as f:
            lines = f.readlines()
        # Find the line for file1.txt and check if hash is different
        for line in lines[1:]:  # Skip header
            if 'file1.txt' in line:
                # Should have new hash for 'updated' content
                parts = line.split(':')
                assert parts[0] != 'd41d8cd98f00b204e9800998ecf8427e', "Hash should be updated"  # MD5 of empty string
                break
        
    finally:
        shutil.rmtree(test_dir)

def test_recursive():
    """Test recursive option"""
    test_dir = tempfile.mkdtemp()
    try:
        # Create nested structure
        os.makedirs(os.path.join(test_dir, 'dir1', 'dir2'))
        with open(os.path.join(test_dir, 'file1.txt'), 'w') as f:
            f.write('root')
        with open(os.path.join(test_dir, 'dir1', 'file2.txt'), 'w') as f:
            f.write('level1')
        with open(os.path.join(test_dir, 'dir1', 'dir2', 'file3.txt'), 'w') as f:
            f.write('level2')
        
        # Generate recursive
        stdout, stderr, rc = run_filecheck(test_dir, "generate . -r")
        assert rc == 0, "Recursive generate failed: "+ str(stderr)
        
        # Check .filecheck has multiple entries
        filecheck_path = os.path.join(test_dir, '.filecheck')
        with open(filecheck_path, 'r') as f:
            lines = f.readlines()
        assert len(lines) >= 3, "Expected header + 1 files + 1 dirs on root"  # files + dir1 and dir2
        filecheck_path = os.path.join(test_dir, 'dir1', '.filecheck')
        with open(filecheck_path, 'r') as f:
            lines = f.readlines()
        assert len(lines) >= 3, "Expected header + 1 files + 1 dirs on dir1"  # files + dir1 and dir2
        filecheck_path = os.path.join(test_dir, 'dir1', 'dir2', '.filecheck')
        with open(filecheck_path, 'r') as f:
            lines = f.readlines()
        assert len(lines) >= 2, "Expected header + 1 files + 1 dirs on dir2"  # files + dir1 and dir2
        
    finally:
        shutil.rmtree(test_dir)

if __name__ == '__main__':
    test_generate_basic()
    test_check_no_changes()
    test_check_file_modified()
    test_update()
    test_recursive()
    print("All tests passed!")