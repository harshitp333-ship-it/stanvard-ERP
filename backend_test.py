#!/usr/bin/env python3
"""
Backend testing for Stanvard ERP - July 18 2026 changes
Tests:
1. OWNER-ONLY DISCOUNT APPROVAL
2. 10-MONTH DEFAULT COLLECTION
3. INSTALLMENT-AWARE FEE SCHEDULE
4. REPORTS with monthly_status
5. REGRESSION: non-discount payment
"""

import requests
import json
from datetime import datetime

# Read backend URL from frontend/.env
with open('/app/frontend/.env', 'r') as f:
    for line in f:
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=')[1].strip() + '/api'
            break

print(f"Testing backend at: {BASE_URL}")

# Test credentials
OWNER_EMAIL = "satya.mundra@stanvard.school"
OWNER_PASSWORD = "Mundra@Satya2026"
SUPER_ADMIN_EMAIL = "superadmin@stanvard.school"
SUPER_ADMIN_PASSWORD = "Stanvard@2026"
ACCOUNTANT_EMAIL = "accountant@stanvard.school"
ACCOUNTANT_PASSWORD = "Accountant@2026"

def login(email, password):
    """Login and return access token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"❌ Login failed for {email}: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get('access_token')

def get_headers(token, school_id=None):
    """Get authorization headers"""
    headers = {"Authorization": f"Bearer {token}"}
    if school_id:
        headers["X-School-Id"] = school_id
    return headers

# Test counters
total_tests = 0
passed_tests = 0
failed_tests = 0

def test(name, condition, details=""):
    """Record test result"""
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    if condition:
        passed_tests += 1
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        failed_tests += 1
        print(f"❌ {name}")
        if details:
            print(f"   {details}")

print("\n" + "="*80)
print("SCENARIO 1: OWNER-ONLY DISCOUNT APPROVAL")
print("="*80)

# Login as super_admin (accountants are blocked from discounts)
super_admin_token = login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
test("1a. Super admin login", super_admin_token is not None)

# Get school_id
resp = requests.get(f"{BASE_URL}/auth/my-schools", headers=get_headers(super_admin_token))
school_id = None
if resp.status_code == 200:
    schools = resp.json()
    if schools:
        school_id = schools[0]['id']
        print(f"   Using school: {schools[0]['name']} ({school_id})")

# Get a student for testing
resp = requests.get(f"{BASE_URL}/students?limit=1", headers=get_headers(super_admin_token, school_id))
test("1a. Get students", resp.status_code == 200)
students = resp.json()
if students:
    student = students[0]
    student_id = student['id']
    print(f"   Using student: {student.get('full_name')} ({student_id})")
    
    # Create a pending discount approval (as super_admin, since accountants are blocked)
    payment_data = {
        "student_id": student_id,
        "items": [
            {
                "fee_head_name": "Tuition Fee",
                "period": "April 2026",
                "amount": 1200
            }
        ],
        "discount": 200,
        "discount_reason": "Test discount for owner approval",
        "payment_mode": "cash",
        "application_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }
    
    resp = requests.post(f"{BASE_URL}/payments/collect", json=payment_data, headers=get_headers(super_admin_token, school_id))
    test("1a. Create pending discount approval (as super_admin)", resp.status_code == 200)
    
    if resp.status_code == 200:
        result = resp.json()
        test("1a. Response has status='pending_approval'", result.get('status') == 'pending_approval')
        test("1a. Response has approval_id", 'approval_id' in result)
        
        if 'approval_id' in result:
            approval_id = result['approval_id']
            print(f"   Created approval_id: {approval_id}")
            
            # Try to approve as super_admin (should fail with 403)
            resp = requests.post(
                f"{BASE_URL}/discount-approvals/{approval_id}/approve",
                json={"remark": "Approved by super admin"},
                headers=get_headers(super_admin_token, school_id)
            )
            test("1b. Super admin CANNOT approve (403)", resp.status_code == 403, 
                 f"Expected 403, got {resp.status_code}")
            
            # Try to reject as super_admin (should fail with 403)
            resp = requests.post(
                f"{BASE_URL}/discount-approvals/{approval_id}/reject",
                json={"remark": "Rejected by super admin"},
                headers=get_headers(super_admin_token, school_id)
            )
            test("1c. Super admin CANNOT reject (403)", resp.status_code == 403,
                 f"Expected 403, got {resp.status_code}")
            
            # Super admin can still LIST approvals
            resp = requests.get(
                f"{BASE_URL}/discount-approvals?status=pending",
                headers=get_headers(super_admin_token, school_id)
            )
            test("1d. Super admin CAN list pending approvals (200)", resp.status_code == 200)
            if resp.status_code == 200:
                approvals = resp.json()
                test("1d. Approval appears in list", any(a.get('id') == approval_id for a in approvals))
            
            # Login as owner
            owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
            test("1e. Owner login", owner_token is not None)
            
            # Owner approves
            resp = requests.post(
                f"{BASE_URL}/discount-approvals/{approval_id}/approve",
                json={"remark": "ok"},
                headers=get_headers(owner_token, school_id)
            )
            test("1e. Owner CAN approve (200)", resp.status_code == 200,
                 f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
            
            if resp.status_code == 200:
                result = resp.json()
                test("1e. Approval status='approved'", result.get('status') == 'approved')
                test("1e. Response has payment_id", 'payment_id' in result or result.get('status') == 'approved')
                
                # Login as accountant for collection
                accountant_token = login(ACCOUNTANT_EMAIL, ACCOUNTANT_PASSWORD)
                test("1f. Accountant login", accountant_token is not None)
                
                # Accountant collects the approved payment
                resp = requests.post(
                    f"{BASE_URL}/discount-approvals/{approval_id}/collect",
                    json={"payment_mode": "cash"},
                    headers=get_headers(accountant_token, school_id))
                test("1f. Accountant collects approved payment (200)", resp.status_code == 200,
                     f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
                
                if resp.status_code == 200:
                    result = resp.json()
                    test("1f. Collection status='collected'", result.get('status') == 'collected')
                    test("1f. Response has payment_id", 'payment_id' in result)
                    test("1f. Response has receipt_number", 'receipt_number' in result)

print("\n" + "="*80)
print("SCENARIO 2: 10-MONTH DEFAULT COLLECTION")
print("="*80)

# Get a student
resp = requests.get(f"{BASE_URL}/students?limit=5", headers=get_headers(super_admin_token, school_id))
if resp.status_code == 200:
    students = resp.json()
    if len(students) >= 2:
        test_student = students[1]  # Use second student
        student_id = test_student['id']
        print(f"   Using student: {test_student.get('full_name')} ({student_id})")
        
        # Create assignment WITHOUT collection_months
        assignment_data = {
            "student_id": student_id,
            "academic_session": "2026-27",
            "fee_plan_id": None,
            "custom_items": [
                {
                    "fee_head_name": "Test Fee",
                    "amount": 10000,
                    "frequency": "monthly"
                }
            ],
            "is_draft": False
        }
        
        resp = requests.post(f"{BASE_URL}/fees/assignments", json=assignment_data, headers=get_headers(super_admin_token, school_id))
        test("2. Create assignment without collection_months (200)", resp.status_code == 200,
             f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
        
        if resp.status_code == 200:
            result = resp.json()
            collection_months = result.get('collection_months', [])
            expected_months = [4, 5, 7, 8, 9, 10, 11, 12, 1, 2]
            test("2. collection_months defaults to 10 months (no 6, no 3)", 
                 collection_months == expected_months,
                 f"Expected {expected_months}, got {collection_months}")
            
            # Clean up
            assignment_id = result.get('id')
            if assignment_id:
                resp = requests.delete(f"{BASE_URL}/fees/assignments/{assignment_id}", headers=get_headers(super_admin_token, school_id))
                test("2. Cleanup: Delete assignment", resp.status_code == 200)

print("\n" + "="*80)
print("SCENARIO 3: INSTALLMENT-AWARE FEE SCHEDULE")
print("="*80)

# Get a fresh student (use third student)
resp = requests.get(f"{BASE_URL}/students?limit=10", headers=get_headers(super_admin_token, school_id))
if resp.status_code == 200:
    students = resp.json()
    if len(students) >= 3:
        test_student = students[2]
        student_id = test_student['id']
        print(f"   Using student: {test_student.get('full_name')} ({student_id})")
        
        # First, delete any existing assignments for this student
        resp = requests.get(f"{BASE_URL}/fees/assignments?student_id={student_id}", headers=get_headers(super_admin_token, school_id))
        if resp.status_code == 200:
            existing = resp.json()
            for assign in existing:
                if assign.get('academic_session') == '2026-27':
                    requests.delete(f"{BASE_URL}/fees/assignments/{assign['id']}", headers=get_headers(super_admin_token))
        
        # Create assignment with one_time fee in April only
        assignment_data = {
            "student_id": student_id,
            "academic_session": "2026-27",
            "fee_plan_id": None,
            "custom_items": [
                {
                    "fee_head_name": "Annual Charge",
                    "amount": 5000,
                    "frequency": "one_time"
                }
            ],
            "collection_months": [4],
            "installments": [
                {"month": 4, "year": 2026, "amount": 5000, "due_date": "2026-04-15", "last_payment_date": "2026-04-30", "label": None, "status": "active"},
                {"month": 5, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 6, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 7, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 8, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 9, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 10, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 11, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 12, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 1, "year": 2027, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 2, "year": 2027, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"},
                {"month": 3, "year": 2027, "amount": 0, "due_date": None, "last_payment_date": None, "label": None, "status": "skip"}
            ],
            "is_draft": False
        }
        
        resp = requests.post(f"{BASE_URL}/fees/assignments", json=assignment_data, headers=get_headers(super_admin_token, school_id))
        test("3a. Create one_time assignment (200)", resp.status_code == 200,
             f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
        
        assignment_id_1 = None
        if resp.status_code == 200:
            result = resp.json()
            assignment_id_1 = result.get('id')
            
            # Get fee-schedule
            resp = requests.get(f"{BASE_URL}/fees/student/{student_id}/fee-schedule", headers=get_headers(super_admin_token, school_id))
            test("3a. Get fee-schedule (200)", resp.status_code == 200)
            
            if resp.status_code == 200:
                schedule_data = resp.json()
                schedule = schedule_data.get('schedule', [])
                active_months = schedule_data.get('active_months', 0)
                
                test("3a. Schedule has 12 months", len(schedule) == 12)
                test("3a. active_months = 1", active_months == 1,
                     f"Expected 1, got {active_months}")
                
                # Check April has amount 5000
                april = next((m for m in schedule if m.get('month') == 4), None)
                if april:
                    test("3a. April amount = 5000", april.get('amount') == 5000,
                         f"Expected 5000, got {april.get('amount')}")
                    test("3a. April status is overdue/pending", april.get('status') in ['overdue', 'pending'])
                
                # Check other months are 'no_fee'
                other_months = [m for m in schedule if m.get('month') != 4]
                all_no_fee = all(m.get('status') == 'no_fee' and m.get('amount') == 0 for m in other_months)
                test("3a. All other months status='no_fee' amount=0", all_no_fee)
            
            # Get dues
            resp = requests.get(f"{BASE_URL}/fees/student/{student_id}/dues", headers=get_headers(super_admin_token, school_id))
            test("3a. Get dues (200)", resp.status_code == 200)
            
            if resp.status_code == 200:
                dues_data = resp.json()
                months_total = dues_data.get('months_total', 0)
                monthly_amount = dues_data.get('monthly_amount', 0)
                due_till_date = dues_data.get('due_till_date', 0)
                
                test("3a. months_total = 1", months_total == 1,
                     f"Expected 1, got {months_total}")
                test("3a. monthly_amount = 5000", monthly_amount == 5000,
                     f"Expected 5000, got {monthly_amount}")
                # April has elapsed (today is July 2026), so due_till_date should be 5000
                test("3a. due_till_date reflects April (5000)", due_till_date == 5000,
                     f"Expected 5000, got {due_till_date}")

# Test 10-month assignment with June & March skip
resp = requests.get(f"{BASE_URL}/students?limit=10", headers=get_headers(super_admin_token, school_id))
if resp.status_code == 200:
    students = resp.json()
    if len(students) >= 4:
        test_student = students[3]
        student_id_2 = test_student['id']
        print(f"   Using student for 10-month test: {test_student.get('full_name')} ({student_id_2})")
        
        # Delete existing assignments
        resp = requests.get(f"{BASE_URL}/fees/assignments?student_id={student_id_2}", headers=get_headers(super_admin_token, school_id))
        if resp.status_code == 200:
            existing = resp.json()
            for assign in existing:
                if assign.get('academic_session') == '2026-27':
                    requests.delete(f"{BASE_URL}/fees/assignments/{assign['id']}", headers=get_headers(super_admin_token))
        
        # Create 10-month assignment
        assignment_data = {
            "student_id": student_id_2,
            "academic_session": "2026-27",
            "fee_plan_id": None,
            "custom_items": [
                {
                    "fee_head_name": "Tuition",
                    "amount": 10000,
                    "frequency": "monthly"
                }
            ],
            "collection_months": [4, 5, 7, 8, 9, 10, 11, 12, 1, 2],
            "installments": [
                {"month": 4, "year": 2026, "amount": 1000, "due_date": "2026-04-15", "last_payment_date": "2026-04-30", "status": "active"},
                {"month": 5, "year": 2026, "amount": 1000, "due_date": "2026-05-15", "last_payment_date": "2026-05-31", "status": "active"},
                {"month": 6, "year": 2026, "amount": 0, "due_date": None, "last_payment_date": None, "status": "skip"},
                {"month": 7, "year": 2026, "amount": 1000, "due_date": "2026-07-15", "last_payment_date": "2026-07-31", "status": "active"},
                {"month": 8, "year": 2026, "amount": 1000, "due_date": "2026-08-15", "last_payment_date": "2026-08-31", "status": "active"},
                {"month": 9, "year": 2026, "amount": 1000, "due_date": "2026-09-15", "last_payment_date": "2026-09-30", "status": "active"},
                {"month": 10, "year": 2026, "amount": 1000, "due_date": "2026-10-15", "last_payment_date": "2026-10-31", "status": "active"},
                {"month": 11, "year": 2026, "amount": 1000, "due_date": "2026-11-15", "last_payment_date": "2026-11-30", "status": "active"},
                {"month": 12, "year": 2026, "amount": 1000, "due_date": "2026-12-15", "last_payment_date": "2026-12-31", "status": "active"},
                {"month": 1, "year": 2027, "amount": 1000, "due_date": "2027-01-15", "last_payment_date": "2027-01-31", "status": "active"},
                {"month": 2, "year": 2027, "amount": 1000, "due_date": "2027-02-15", "last_payment_date": "2027-02-28", "status": "active"},
                {"month": 3, "year": 2027, "amount": 0, "due_date": None, "last_payment_date": None, "status": "skip"}
            ],
            "is_draft": False
        }
        
        resp = requests.post(f"{BASE_URL}/fees/assignments", json=assignment_data, headers=get_headers(super_admin_token, school_id))
        test("3b. Create 10-month assignment (200)", resp.status_code == 200,
             f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
        
        assignment_id_2 = None
        if resp.status_code == 200:
            result = resp.json()
            assignment_id_2 = result.get('id')
            
            # Get fee-schedule
            resp = requests.get(f"{BASE_URL}/fees/student/{student_id_2}/fee-schedule", headers=get_headers(super_admin_token, school_id))
            test("3b. Get fee-schedule (200)", resp.status_code == 200)
            
            if resp.status_code == 200:
                schedule_data = resp.json()
                schedule = schedule_data.get('schedule', [])
                active_months = schedule_data.get('active_months', 0)
                
                test("3b. active_months = 10", active_months == 10,
                     f"Expected 10, got {active_months}")
                
                # Check June is 'no_fee'
                june = next((m for m in schedule if m.get('month') == 6), None)
                if june:
                    test("3b. June status='no_fee'", june.get('status') == 'no_fee')
                    test("3b. June amount=0", june.get('amount') == 0)
                
                # Check March is 'no_fee'
                march = next((m for m in schedule if m.get('month') == 3), None)
                if march:
                    test("3b. March status='no_fee'", march.get('status') == 'no_fee')
                    test("3b. March amount=0", march.get('amount') == 0)
                
                # Check active months have amount 1000
                active = [m for m in schedule if m.get('status') != 'no_fee']
                all_1000 = all(m.get('amount') == 1000 for m in active)
                test("3b. All active months amount=1000", all_1000)
            
            # Get dues
            resp = requests.get(f"{BASE_URL}/fees/student/{student_id_2}/dues", headers=get_headers(super_admin_token, school_id))
            test("3b. Get dues (200)", resp.status_code == 200)
            
            if resp.status_code == 200:
                dues_data = resp.json()
                months_total = dues_data.get('months_total', 0)
                
                test("3b. months_total = 10", months_total == 10,
                     f"Expected 10, got {months_total}")
        
        # Clean up both assignments
        if assignment_id_1:
            resp = requests.delete(f"{BASE_URL}/fees/assignments/{assignment_id_1}", headers=get_headers(super_admin_token))
            test("3. Cleanup: Delete assignment 1", resp.status_code == 200)
        
        if assignment_id_2:
            resp = requests.delete(f"{BASE_URL}/fees/assignments/{assignment_id_2}", headers=get_headers(super_admin_token))
            test("3. Cleanup: Delete assignment 2", resp.status_code == 200)

print("\n" + "="*80)
print("SCENARIO 4: REPORTS with monthly_status")
print("="*80)

# Get school_id for header
resp = requests.get(f"{BASE_URL}/auth/my-schools", headers=get_headers(super_admin_token))
school_id = None
if resp.status_code == 200:
    schools = resp.json()
    if schools:
        school_id = schools[0].get('id')

headers = get_headers(super_admin_token)
if school_id:
    headers['X-School-Id'] = school_id

resp = requests.get(f"{BASE_URL}/reports/fee-status", headers=headers)
test("4. Get fee-status report (200)", resp.status_code == 200)

if resp.status_code == 200:
    data = resp.json()
    rows = data.get('rows', [])
    test("4. Report has rows", len(rows) > 0)
    
    if rows:
        # Check if any row has monthly_status
        sample_row = rows[0]
        test("4. Row has monthly_status field", 'monthly_status' in sample_row)
        
        if 'monthly_status' in sample_row:
            monthly_status = sample_row.get('monthly_status', [])
            test("4. monthly_status is array", isinstance(monthly_status, list))
            
            # Check if any month has 'no_fee' status
            has_no_fee = any(m.get('status') == 'no_fee' for m in monthly_status)
            print(f"   Found 'no_fee' entries: {has_no_fee}")

print("\n" + "="*80)
print("SCENARIO 5: REGRESSION - Non-discount payment")
print("="*80)

# Login as accountant
accountant_token = login(ACCOUNTANT_EMAIL, ACCOUNTANT_PASSWORD)

# Get a student
resp = requests.get(f"{BASE_URL}/students?limit=1", headers=get_headers(accountant_token, school_id))
if resp.status_code == 200:
    students = resp.json()
    if students:
        student = students[0]
        student_id = student['id']
        
        # Create payment with discount=0
        payment_data = {
            "student_id": student_id,
            "items": [
                {
                    "fee_head_name": "Test Fee",
                    "period": "July 2026",
                    "amount": 500
                }
            ],
            "discount": 0,
            "payment_mode": "cash"
        }
        
        resp = requests.post(f"{BASE_URL}/payments/collect", json=payment_data, headers=get_headers(accountant_token, school_id))
        test("5. Non-discount payment (200)", resp.status_code == 200,
             f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}")
        
        if resp.status_code == 200:
            result = resp.json()
            test("5. Response has status='success'", result.get('status') == 'success')
            test("5. Response has receipt_number", 'receipt_number' in result)

print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)
print(f"Total tests: {total_tests}")
print(f"Passed: {passed_tests} ({passed_tests*100//total_tests if total_tests > 0 else 0}%)")
print(f"Failed: {failed_tests}")
print("="*80)

if failed_tests == 0:
    print("✅ ALL TESTS PASSED")
else:
    print(f"❌ {failed_tests} TEST(S) FAILED")
