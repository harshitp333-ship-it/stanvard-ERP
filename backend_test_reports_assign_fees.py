#!/usr/bin/env python3
"""
Test script for FEATURE BATCH (Jul 2026) — Reports enhancements + Assign Fees redesign

Tests 5 areas:
A) /api/reports/fee-status (new fields: due_till_date, overdue_amount, overdue_months, monthly_amount)
B) /api/reports/fee-status.xlsx (Excel export with new columns)
C) /api/reports/fee-status.pdf (PDF export)
D) /api/reports/fee-status.csv (CSV export with new columns)
E) /api/fees/assignments CRUD with new fields (discount_reason, internal_notes)
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://code-standard-1.preview.emergentagent.com/api"
SUPER_ADMIN_EMAIL = "superadmin@stanvard.school"
SUPER_ADMIN_PASSWORD = "Stanvard@2026"
SCHOOL_ID = "034cab3a-3107-4cf2-bfdb-3bba434a5367"

# Test results
test_results = {
    "A": {"total": 0, "passed": 0, "failed": 0, "tests": []},
    "B": {"total": 0, "passed": 0, "failed": 0, "tests": []},
    "C": {"total": 0, "passed": 0, "failed": 0, "tests": []},
    "D": {"total": 0, "passed": 0, "failed": 0, "tests": []},
    "E": {"total": 0, "passed": 0, "failed": 0, "tests": []},
}

def log_test(section, test_name, passed, details=""):
    """Log a test result"""
    test_results[section]["total"] += 1
    if passed:
        test_results[section]["passed"] += 1
        status = "✓"
    else:
        test_results[section]["failed"] += 1
        status = "✗"
    
    test_results[section]["tests"].append({
        "name": test_name,
        "passed": passed,
        "details": details
    })
    print(f"  {status} {test_name}")
    if details and not passed:
        print(f"    Details: {details}")

def login():
    """Login as super admin and return token + headers"""
    print("\n=== LOGIN ===")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
    )
    
    if response.status_code != 200:
        print(f"✗ Login failed: {response.status_code}")
        print(f"  Response: {response.text}")
        sys.exit(1)
    
    data = response.json()
    token = data.get("access_token")
    
    if not token:
        print(f"✗ No access token in response")
        sys.exit(1)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-School-Id": SCHOOL_ID,
        "Content-Type": "application/json"
    }
    
    print(f"✓ Logged in as {SUPER_ADMIN_EMAIL}")
    return headers

def test_section_a(headers):
    """Test A: /api/reports/fee-status with new fields"""
    print("\n=== SECTION A: /api/reports/fee-status (new fields) ===")
    
    # A1: Get fee status report
    response = requests.get(f"{BASE_URL}/reports/fee-status", headers=headers)
    
    if response.status_code != 200:
        log_test("A", "GET /api/reports/fee-status returns 200", False, 
                f"Status: {response.status_code}, Body: {response.text[:200]}")
        return
    
    log_test("A", "GET /api/reports/fee-status returns 200", True)
    
    data = response.json()
    rows = data.get("rows", [])
    summary = data.get("summary", {})
    
    if not rows:
        log_test("A", "Response has rows", False, "No rows in response")
        return
    
    log_test("A", "Response has rows", True, f"Found {len(rows)} rows")
    
    # A2: Check first row has all new fields
    first_row = rows[0]
    required_fields = ["due_till_date", "overdue_amount", "overdue_months", "monthly_amount"]
    
    missing_fields = [f for f in required_fields if f not in first_row]
    if missing_fields:
        log_test("A", "Row has all new fields (due_till_date, overdue_amount, overdue_months, monthly_amount)", 
                False, f"Missing fields: {missing_fields}")
    else:
        log_test("A", "Row has all new fields (due_till_date, overdue_amount, overdue_months, monthly_amount)", True)
    
    # A3: Check summary has total_due_till_date
    if "total_due_till_date" not in summary:
        log_test("A", "Summary has total_due_till_date", False, f"Summary keys: {list(summary.keys())}")
    else:
        log_test("A", "Summary has total_due_till_date", True, 
                f"total_due_till_date = {summary['total_due_till_date']}")
    
    # A4: Find a student with fully unpaid fees (paid == 0 and expected > 0)
    # Looking for Deepika Gameti KNP-0000 or similar
    unpaid_student = None
    for row in rows:
        if row.get("paid", 0) == 0 and row.get("expected", 0) > 0:
            unpaid_student = row
            break
    
    if not unpaid_student:
        log_test("A", "Find unpaid student for due_till_date validation", False, 
                "No student with paid=0 and expected>0 found")
    else:
        student_name = unpaid_student.get("full_name", "Unknown")
        admission_no = unpaid_student.get("admission_number", "Unknown")
        log_test("A", "Find unpaid student for due_till_date validation", True, 
                f"Found: {student_name} ({admission_no})")
        
        # A5: Validate due_till_date calculation
        # Today is 2026-07-10 which is BEFORE the 15th
        # So due_till_date should include April, May, June only (3 months)
        # due_till_date should be approximately 3 * monthly_amount
        
        due_till_date = unpaid_student.get("due_till_date", 0)
        monthly_amount = unpaid_student.get("monthly_amount", 0)
        expected_due = 3 * monthly_amount
        
        # Allow ±1 rupee tolerance
        if abs(due_till_date - expected_due) <= 1:
            log_test("A", f"due_till_date ~= 3 * monthly_amount (April+May+June only, NOT July)", True,
                    f"due_till_date={due_till_date:.2f}, 3*monthly={expected_due:.2f}, diff={abs(due_till_date - expected_due):.2f}")
        else:
            log_test("A", f"due_till_date ~= 3 * monthly_amount (April+May+June only, NOT July)", False,
                    f"due_till_date={due_till_date:.2f}, 3*monthly={expected_due:.2f}, diff={abs(due_till_date - expected_due):.2f}")
        
        # A6: Verify due_till_date <= overdue_amount + 1 (they are aliases)
        overdue_amount = unpaid_student.get("overdue_amount", 0)
        if abs(due_till_date - overdue_amount) <= 1:
            log_test("A", "due_till_date <= overdue_amount + 1 (they are aliases)", True,
                    f"due_till_date={due_till_date:.2f}, overdue_amount={overdue_amount:.2f}")
        else:
            log_test("A", "due_till_date <= overdue_amount + 1 (they are aliases)", False,
                    f"due_till_date={due_till_date:.2f}, overdue_amount={overdue_amount:.2f}, diff={abs(due_till_date - overdue_amount):.2f}")

def test_section_b(headers):
    """Test B: /api/reports/fee-status.xlsx (Excel export)"""
    print("\n=== SECTION B: /api/reports/fee-status.xlsx (Excel export) ===")
    
    # B1: Get Excel export
    response = requests.get(f"{BASE_URL}/reports/fee-status.xlsx", headers=headers)
    
    if response.status_code != 200:
        log_test("B", "GET /api/reports/fee-status.xlsx returns 200", False,
                f"Status: {response.status_code}")
        return
    
    log_test("B", "GET /api/reports/fee-status.xlsx returns 200", True)
    
    # B2: Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "spreadsheet" in content_type or "excel" in content_type:
        log_test("B", "Content-Type is Excel/spreadsheet", True, f"Content-Type: {content_type}")
    else:
        log_test("B", "Content-Type is Excel/spreadsheet", False, f"Content-Type: {content_type}")
    
    # B3: Check body is non-empty
    body_size = len(response.content)
    if body_size > 0:
        log_test("B", "Response body is non-empty", True, f"Size: {body_size} bytes")
    else:
        log_test("B", "Response body is non-empty", False)
        return
    
    # B4: Try to load workbook with openpyxl
    try:
        from io import BytesIO
        import openpyxl
        
        wb = openpyxl.load_workbook(BytesIO(response.content))
        log_test("B", "Workbook loads successfully with openpyxl", True)
        
        # B5: Get first sheet and read headers
        ws = wb.active
        headers_row = []
        for cell in ws[1]:
            headers_row.append(cell.value)
        
        log_test("B", "Read row 1 headers", True, f"Found {len(headers_row)} columns")
        
        # B6: Check for required columns
        required_cols = ["Due Till Date (Rs.)", "Overdue Months"]
        missing_cols = [col for col in required_cols if col not in headers_row]
        
        if missing_cols:
            log_test("B", "Headers contain 'Due Till Date (Rs.)' and 'Overdue Months'", False,
                    f"Missing: {missing_cols}")
        else:
            log_test("B", "Headers contain 'Due Till Date (Rs.)' and 'Overdue Months'", True)
        
        # B7: Check column order (should be after 'Paid (Rs.)' and before 'Total Due (Rs.)')
        try:
            paid_idx = headers_row.index("Paid (Rs.)")
            due_till_idx = headers_row.index("Due Till Date (Rs.)")
            overdue_months_idx = headers_row.index("Overdue Months")
            total_due_idx = headers_row.index("Total Due (Rs.)")
            
            if paid_idx < due_till_idx < total_due_idx and paid_idx < overdue_months_idx < total_due_idx:
                log_test("B", "New columns positioned after 'Paid (Rs.)' and before 'Total Due (Rs.)'", True)
            else:
                log_test("B", "New columns positioned after 'Paid (Rs.)' and before 'Total Due (Rs.)'", False,
                        f"Order: Paid={paid_idx}, DueTillDate={due_till_idx}, OverdueMonths={overdue_months_idx}, TotalDue={total_due_idx}")
        except ValueError as e:
            log_test("B", "New columns positioned after 'Paid (Rs.)' and before 'Total Due (Rs.)'", False,
                    f"Column not found: {e}")
        
        # B8: Check second row has values
        row2_values = []
        for cell in ws[2]:
            row2_values.append(cell.value)
        
        if len(row2_values) > 0:
            log_test("B", "Second row has values", True, f"Found {len(row2_values)} values")
            
            # B9: Check Due Till Date column has numeric value
            try:
                due_till_val = row2_values[due_till_idx]
                if isinstance(due_till_val, (int, float)):
                    log_test("B", "Due Till Date column has numeric value in row 2", True, f"Value: {due_till_val}")
                else:
                    log_test("B", "Due Till Date column has numeric value in row 2", False, f"Value: {due_till_val} (type: {type(due_till_val)})")
            except:
                log_test("B", "Due Till Date column has numeric value in row 2", False, "Could not read value")
            
            # B10: Check Overdue Months column has integer value
            try:
                overdue_months_val = row2_values[overdue_months_idx]
                if isinstance(overdue_months_val, int):
                    log_test("B", "Overdue Months column has integer value in row 2", True, f"Value: {overdue_months_val}")
                else:
                    log_test("B", "Overdue Months column has integer value in row 2", False, f"Value: {overdue_months_val} (type: {type(overdue_months_val)})")
            except:
                log_test("B", "Overdue Months column has integer value in row 2", False, "Could not read value")
        else:
            log_test("B", "Second row has values", False)
        
    except ImportError:
        log_test("B", "Load workbook with openpyxl", False, "openpyxl not available")
    except Exception as e:
        log_test("B", "Load workbook with openpyxl", False, f"Error: {str(e)}")

def test_section_c(headers):
    """Test C: /api/reports/fee-status.pdf (PDF export)"""
    print("\n=== SECTION C: /api/reports/fee-status.pdf (PDF export) ===")
    
    # C1: Get PDF export
    response = requests.get(f"{BASE_URL}/reports/fee-status.pdf", headers=headers)
    
    if response.status_code != 200:
        log_test("C", "GET /api/reports/fee-status.pdf returns 200", False,
                f"Status: {response.status_code}")
        return
    
    log_test("C", "GET /api/reports/fee-status.pdf returns 200", True)
    
    # C2: Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "pdf" in content_type.lower():
        log_test("C", "Content-Type is application/pdf", True, f"Content-Type: {content_type}")
    else:
        log_test("C", "Content-Type is application/pdf", False, f"Content-Type: {content_type}")
    
    # C3: Check body size > 30000 bytes
    body_size = len(response.content)
    if body_size > 30000:
        log_test("C", "Content-Length > 30000 bytes", True, f"Size: {body_size} bytes")
    else:
        log_test("C", "Content-Length > 30000 bytes", False, f"Size: {body_size} bytes")
    
    # C4: Check body starts with %PDF-
    if response.content.startswith(b'%PDF-'):
        log_test("C", "Body starts with b'%PDF-'", True)
    else:
        log_test("C", "Body starts with b'%PDF-'", False, f"Starts with: {response.content[:10]}")

def test_section_d(headers):
    """Test D: /api/reports/fee-status.csv (CSV export)"""
    print("\n=== SECTION D: /api/reports/fee-status.csv (CSV export) ===")
    
    # D1: Get CSV export
    response = requests.get(f"{BASE_URL}/reports/fee-status.csv", headers=headers)
    
    if response.status_code != 200:
        log_test("D", "GET /api/reports/fee-status.csv returns 200", False,
                f"Status: {response.status_code}")
        return
    
    log_test("D", "GET /api/reports/fee-status.csv returns 200", True)
    
    # D2: Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "csv" in content_type.lower():
        log_test("D", "Content-Type is text/csv", True, f"Content-Type: {content_type}")
    else:
        log_test("D", "Content-Type is text/csv", False, f"Content-Type: {content_type}")
    
    # D3: Get first line
    lines = response.text.split('\n')
    if not lines:
        log_test("D", "Response has lines", False)
        return
    
    first_line = lines[0]
    log_test("D", "Response has lines", True, f"Found {len(lines)} lines")
    
    # D4: Check first line contains required columns
    required_cols = ["Due Till Date (Rs.)", "Overdue Months", "Total Due (Rs.)"]
    missing_cols = [col for col in required_cols if col not in first_line]
    
    if missing_cols:
        log_test("D", "First line contains 'Due Till Date (Rs.)', 'Overdue Months', 'Total Due (Rs.)'", False,
                f"Missing: {missing_cols}\nFirst line: {first_line[:200]}")
    else:
        log_test("D", "First line contains 'Due Till Date (Rs.)', 'Overdue Months', 'Total Due (Rs.)'", True)
    
    # D5: Check second line has values matching header count (use proper CSV parsing)
    try:
        import csv
        from io import StringIO
        
        reader = csv.reader(StringIO(response.text))
        rows = list(reader)
        
        if len(rows) > 1:
            header_count = len(rows[0])
            value_count = len(rows[1])
            
            if header_count == value_count:
                log_test("D", "Second line values match header count", True,
                        f"Headers: {header_count}, Values: {value_count}")
            else:
                log_test("D", "Second line values match header count", False,
                        f"Headers: {header_count}, Values: {value_count}")
        else:
            log_test("D", "Second line exists", False)
    except Exception as e:
        log_test("D", "Second line values match header count", False, f"Error: {str(e)}")

def test_section_e(headers):
    """Test E: /api/fees/assignments CRUD with new fields (discount_reason, internal_notes)"""
    print("\n=== SECTION E: /api/fees/assignments CRUD (discount_reason, internal_notes) ===")
    
    # E1: Get a fee plan
    response = requests.get(f"{BASE_URL}/fees/plans", headers=headers)
    
    if response.status_code != 200:
        log_test("E", "GET /api/fees/plans returns 200", False, f"Status: {response.status_code}")
        return
    
    plans = response.json()
    if not plans:
        log_test("E", "GET /api/fees/plans returns plans", False, "No plans found")
        return
    
    fee_plan_id = plans[0]["id"]
    log_test("E", "GET /api/fees/plans returns plans", True, f"Using plan_id: {fee_plan_id}")
    
    # E2: Get students to find one not assigned to this plan
    response = requests.get(f"{BASE_URL}/students", headers=headers)
    
    if response.status_code != 200:
        log_test("E", "GET /api/students returns 200", False, f"Status: {response.status_code}")
        return
    
    students = response.json()
    if not students:
        log_test("E", "GET /api/students returns students", False, "No students found")
        return
    
    log_test("E", "GET /api/students returns students", True, f"Found {len(students)} students")
    
    # E3: Try to find a student not assigned to this plan
    student_id = None
    for student in students[:20]:  # Try first 20 students
        sid = student["id"]
        
        # Check if student already has this plan assigned
        check_response = requests.get(f"{BASE_URL}/fees/assignments?student_id={sid}", headers=headers)
        if check_response.status_code == 200:
            assignments = check_response.json()
            has_plan = any(a.get("fee_plan_id") == fee_plan_id for a in assignments)
            
            if not has_plan:
                student_id = sid
                student_name = student.get("full_name", "Unknown")
                log_test("E", "Find student not assigned to selected plan", True, 
                        f"Using student: {student_name} (ID: {student_id})")
                break
    
    if not student_id:
        log_test("E", "Find student not assigned to selected plan", False, 
                "All checked students already have this plan")
        return
    
    # E4: POST /api/fees/assignments with discount_reason and internal_notes
    assignment_data = {
        "student_id": student_id,
        "fee_plan_id": fee_plan_id,
        "discount_percent": 10,
        "discount_reason": "Sibling Discount",
        "remarks": "on receipt",
        "internal_notes": "private staff note"
    }
    
    response = requests.post(f"{BASE_URL}/fees/assignments", headers=headers, json=assignment_data)
    
    if response.status_code != 200:
        log_test("E", "E1: POST /api/fees/assignments with discount_reason and internal_notes", False,
                f"Status: {response.status_code}, Body: {response.text[:200]}")
        return
    
    assignment = response.json()
    assignment_id = assignment.get("id")
    
    # Check if response echoes both new fields
    if assignment.get("discount_reason") == "Sibling Discount" and assignment.get("internal_notes") == "private staff note":
        log_test("E", "E1: POST /api/fees/assignments - response echoes discount_reason and internal_notes", True)
    else:
        log_test("E", "E1: POST /api/fees/assignments - response echoes discount_reason and internal_notes", False,
                f"discount_reason: {assignment.get('discount_reason')}, internal_notes: {assignment.get('internal_notes')}")
    
    # E5: PATCH /api/fees/assignments/{id} with updated fields
    update_data = {
        "discount_reason": "Merit",
        "internal_notes": "updated staff note",
        "discount_percent": 15
    }
    
    response = requests.patch(f"{BASE_URL}/fees/assignments/{assignment_id}", headers=headers, json=update_data)
    
    if response.status_code != 200:
        log_test("E", "E2: PATCH /api/fees/assignments/{id} with updated fields", False,
                f"Status: {response.status_code}, Body: {response.text[:200]}")
    else:
        updated = response.json()
        
        # Check if response has updated fields
        if (updated.get("discount_reason") == "Merit" and 
            updated.get("internal_notes") == "updated staff note" and 
            updated.get("discount_percent") == 15):
            log_test("E", "E2: PATCH /api/fees/assignments/{id} - response has updated fields", True)
        else:
            log_test("E", "E2: PATCH /api/fees/assignments/{id} - response has updated fields", False,
                    f"discount_reason: {updated.get('discount_reason')}, internal_notes: {updated.get('internal_notes')}, discount_percent: {updated.get('discount_percent')}")
    
    # E6: GET /api/fees/assignments?student_id={student_id} to verify update
    response = requests.get(f"{BASE_URL}/fees/assignments?student_id={student_id}", headers=headers)
    
    if response.status_code != 200:
        log_test("E", "E3: GET /api/fees/assignments?student_id={student_id} returns 200", False,
                f"Status: {response.status_code}")
    else:
        assignments = response.json()
        
        # Find our assignment
        our_assignment = None
        for a in assignments:
            if a.get("id") == assignment_id:
                our_assignment = a
                break
        
        if not our_assignment:
            log_test("E", "E3: GET /api/fees/assignments - assignment appears in list", False,
                    "Assignment not found in list")
        else:
            log_test("E", "E3: GET /api/fees/assignments - assignment appears in list with updated fields", True,
                    f"discount_reason: {our_assignment.get('discount_reason')}, internal_notes: {our_assignment.get('internal_notes')}")
    
    # E7: DELETE /api/fees/assignments/{id}
    response = requests.delete(f"{BASE_URL}/fees/assignments/{assignment_id}", headers=headers)
    
    if response.status_code != 200:
        log_test("E", "E4: DELETE /api/fees/assignments/{id} returns 200", False,
                f"Status: {response.status_code}")
    else:
        log_test("E", "E4: DELETE /api/fees/assignments/{id} returns 200", True)
    
    # E8: Verify assignment is deleted
    response = requests.get(f"{BASE_URL}/fees/assignments?student_id={student_id}", headers=headers)
    
    if response.status_code == 200:
        assignments = response.json()
        still_exists = any(a.get("id") == assignment_id for a in assignments)
        
        if not still_exists:
            log_test("E", "E4: GET /api/fees/assignments - deleted assignment no longer in list", True)
        else:
            log_test("E", "E4: GET /api/fees/assignments - deleted assignment no longer in list", False,
                    "Assignment still exists after delete")
    else:
        log_test("E", "E4: GET /api/fees/assignments after delete", False,
                f"Status: {response.status_code}")
    
    # E9: Regression - POST assignment with NO discount_reason and NO internal_notes (both optional)
    regression_data = {
        "student_id": student_id,
        "fee_plan_id": fee_plan_id,
        "discount_percent": 0,
        "remarks": "regression test"
    }
    
    response = requests.post(f"{BASE_URL}/fees/assignments", headers=headers, json=regression_data)
    
    if response.status_code != 200:
        log_test("E", "E5: Regression - POST assignment without discount_reason/internal_notes succeeds", False,
                f"Status: {response.status_code}, Body: {response.text[:200]}")
    else:
        regression_assignment = response.json()
        regression_id = regression_assignment.get("id")
        log_test("E", "E5: Regression - POST assignment without discount_reason/internal_notes succeeds", True,
                "Both fields are optional and nullable")
        
        # Clean up
        requests.delete(f"{BASE_URL}/fees/assignments/{regression_id}", headers=headers)

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    
    for section in ["A", "B", "C", "D", "E"]:
        results = test_results[section]
        total_tests += results["total"]
        total_passed += results["passed"]
        total_failed += results["failed"]
        
        print(f"\nSection {section}: {results['passed']}/{results['total']} passed")
        
        # Show failed tests
        failed_tests = [t for t in results["tests"] if not t["passed"]]
        if failed_tests:
            for test in failed_tests:
                print(f"  ✗ {test['name']}")
                if test['details']:
                    print(f"    {test['details']}")
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {total_passed}/{total_tests} tests passed ({total_passed*100//total_tests if total_tests > 0 else 0}%)")
    print(f"{'='*80}\n")
    
    return total_failed == 0

def main():
    """Main test runner"""
    print("="*80)
    print("FEATURE BATCH (Jul 2026) — Reports enhancements + Assign Fees redesign")
    print("Testing 5 areas: A, B, C, D, E")
    print("="*80)
    
    # Login
    headers = login()
    
    # Run tests
    test_section_a(headers)
    test_section_b(headers)
    test_section_c(headers)
    test_section_d(headers)
    test_section_e(headers)
    
    # Print summary
    success = print_summary()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
