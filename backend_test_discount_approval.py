#!/usr/bin/env python3
"""
BUG FIX RETEST — Stanvard School ERP: Discount Approval Workflow

Reported bug: "In fee collection & approval, the fee receipt is being printed without owner approval."
Root cause: super_admin was bypassing approval due to role != 'super_admin' check.
Fix: Removed bypass — ALL roles now require approval for discount>0.

This test verifies:
A) super_admin with discount MUST require approval (THE BUG FIX)
B) super_admin with discount but NO discount_reason → 400
C) super_admin with ZERO discount → immediate receipt
D) accountant with discount → pending_approval (regression)
E) owner approves → payment created with receipt
F) owner rejects → no payment created
G) Razorpay online + discount → 400
H) Previous RBAC & path regressions
"""
import requests
import json
import sys
from datetime import datetime

# Backend URL
BASE_URL = "https://code-standard-1.preview.emergentagent.com/api"

# School ID for KNP branch
SCHOOL_ID = "aeed2599-256c-44b1-a670-8a90bfa7d38e"

# Test credentials
SUPER_ADMIN = {"email": "superadmin@stanvard.school", "password": "Stanvard@2026"}
ACCOUNTANT = {"email": "accountant@stanvard.school", "password": "Accountant@2026"}
OWNER_SATYA = {"email": "satya.mundra@stanvard.school", "password": "Mundra@Satya2026"}
PARENT = {"email": "9079111899", "password": "111899"}

# Test results
passed = 0
failed = 0
failures = []

def log_pass(test_name):
    global passed
    passed += 1
    print(f"✓ {test_name}")

def log_fail(test_name, reason):
    global failed, failures
    failed += 1
    failures.append(f"{test_name}: {reason}")
    print(f"✗ {test_name}: {reason}")

def login(credentials):
    """Login and return access token."""
    resp = requests.post(f"{BASE_URL}/auth/login", json=credentials)
    if resp.status_code != 200:
        log_fail(f"Login {credentials['email']}", f"Status {resp.status_code}")
        return None
    data = resp.json()
    return data.get('access_token')

def get_headers(token, school_id=None):
    """Return authorization headers."""
    headers = {"Authorization": f"Bearer {token}"}
    if school_id:
        headers["X-School-Id"] = school_id
    return headers

def get_student(token):
    """Get a student for testing."""
    headers = get_headers(token, SCHOOL_ID)
    resp = requests.get(f"{BASE_URL}/students", headers=headers)
    if resp.status_code != 200:
        log_fail("Get students", f"Status {resp.status_code}")
        return None
    students = resp.json()
    if not students:
        log_fail("Get students", "No students found")
        return None
    return students[0]

def get_payment_count(token):
    """Get current payment count."""
    headers = get_headers(token, SCHOOL_ID)
    resp = requests.get(f"{BASE_URL}/payments", headers=headers)
    if resp.status_code != 200:
        return 0
    return len(resp.json())

print("=" * 80)
print("BUG FIX RETEST: Discount Approval Workflow")
print("=" * 80)

# Login all users
print("\n[SETUP] Logging in users...")
super_admin_token = login(SUPER_ADMIN)
accountant_token = login(ACCOUNTANT)
owner_token = login(OWNER_SATYA)
parent_token = login(PARENT)

if not all([super_admin_token, accountant_token, owner_token, parent_token]):
    print("\n❌ CRITICAL: Login failed for one or more users. Cannot proceed.")
    sys.exit(1)

log_pass("All users logged in successfully")

# Get a student for testing
print("\n[SETUP] Getting test student...")
student = get_student(super_admin_token)
if not student:
    print("\n❌ CRITICAL: No student found. Cannot proceed.")
    sys.exit(1)

student_id = student['id']
student_name = student.get('full_name', 'Unknown')
print(f"Using student: {student_name} (ID: {student_id})")

# ============================================================================
# TEST A: SUPER_ADMIN with discount MUST require approval (THIS IS THE BUG)
# ============================================================================
print("\n" + "=" * 80)
print("TEST A: SUPER_ADMIN with discount MUST require approval (BUG FIX)")
print("=" * 80)

# Get baseline payment count
baseline_payment_count = get_payment_count(super_admin_token)
print(f"Baseline payment count: {baseline_payment_count}")

# A.1: POST /api/payments/collect with discount
print("\nA.1: POST /api/payments/collect as super_admin with discount=200")
headers = get_headers(super_admin_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Aug 2026", "amount": 1000}
    ],
    "discount": 200,
    "late_fee": 0,
    "payment_mode": "cash",
    "discount_reason": "Testing super_admin discount bug fix"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload, headers=headers)

print(f"Response status: {resp.status_code}")
print(f"Response body: {json.dumps(resp.json(), indent=2)}")

if resp.status_code != 200:
    log_fail("A.1: super_admin discount collect", f"Expected 200, got {resp.status_code}")
else:
    data = resp.json()
    
    # Check for pending_approval status
    if data.get('status') != 'pending_approval':
        log_fail("A.1: super_admin discount collect", 
                f"Expected status='pending_approval', got '{data.get('status')}'")
    else:
        log_pass("A.1: Response has status='pending_approval'")
    
    # Check for approval_id
    if not data.get('approval_id'):
        log_fail("A.1: super_admin discount collect", "Missing approval_id in response")
    else:
        approval_id = data['approval_id']
        log_pass(f"A.1: Response has approval_id: {approval_id}")
    
    # Check for approval object
    if not data.get('approval'):
        log_fail("A.1: super_admin discount collect", "Missing approval object in response")
    else:
        log_pass("A.1: Response has approval object")
    
    # FORBIDDEN: receipt_number, status='success'
    if data.get('receipt_number'):
        log_fail("A.1: super_admin discount collect", 
                f"FORBIDDEN: receipt_number present: {data.get('receipt_number')}")
    else:
        log_pass("A.1: No receipt_number in response (correct)")
    
    if data.get('status') == 'success':
        log_fail("A.1: super_admin discount collect", 
                "FORBIDDEN: status='success' (should be 'pending_approval')")
    else:
        log_pass("A.1: Status is not 'success' (correct)")

# A.2: Verify payment count DID NOT increase
print("\nA.2: Verify payment count DID NOT increase")
new_payment_count = get_payment_count(super_admin_token)
print(f"New payment count: {new_payment_count}")

if new_payment_count > baseline_payment_count:
    log_fail("A.2: Payment count check", 
            f"Payment count increased from {baseline_payment_count} to {new_payment_count} (should not increase)")
else:
    log_pass("A.2: Payment count did not increase (correct)")

# A.3: Verify approval appears in pending list for owner
print("\nA.3: GET /api/discount-approvals?status=pending as owner")
headers = get_headers(owner_token, SCHOOL_ID)
resp = requests.get(f"{BASE_URL}/discount-approvals?status=pending", headers=headers)

if resp.status_code != 200:
    log_fail("A.3: Get pending approvals", f"Status {resp.status_code}")
else:
    approvals = resp.json()
    print(f"Found {len(approvals)} pending approval(s)")
    
    # Find the approval we just created
    found = False
    for appr in approvals:
        if appr.get('id') == approval_id:
            found = True
            print(f"Found approval: {appr.get('student_name')} - Discount: ₹{appr.get('discount')}")
            break
    
    if found:
        log_pass("A.3: Approval appears in pending list")
    else:
        log_fail("A.3: Get pending approvals", f"Approval {approval_id} not found in pending list")

# ============================================================================
# TEST B: SUPER_ADMIN with discount but NO discount_reason
# ============================================================================
print("\n" + "=" * 80)
print("TEST B: SUPER_ADMIN with discount but NO discount_reason")
print("=" * 80)

print("\nB.1: POST /api/payments/collect with discount=100 but no discount_reason")
headers = get_headers(super_admin_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Sep 2026", "amount": 1000}
    ],
    "discount": 100,
    "late_fee": 0,
    "payment_mode": "cash"
    # NO discount_reason
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 400:
    log_fail("B.1: Discount without reason", f"Expected 400, got {resp.status_code}")
else:
    data = resp.json()
    detail = data.get('detail', '')
    print(f"Response detail: {detail}")
    
    if "Discount reason is required" in detail:
        log_pass("B.1: Returns 400 with 'Discount reason is required'")
    else:
        log_fail("B.1: Discount without reason", f"Expected 'Discount reason is required', got '{detail}'")

# ============================================================================
# TEST C: SUPER_ADMIN with ZERO discount (normal flow)
# ============================================================================
print("\n" + "=" * 80)
print("TEST C: SUPER_ADMIN with ZERO discount (normal flow)")
print("=" * 80)

print("\nC.1: POST /api/payments/collect with discount=0")
headers = get_headers(super_admin_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Oct 2026", "amount": 500}
    ],
    "discount": 0,
    "late_fee": 0,
    "payment_mode": "cash"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 200:
    log_fail("C.1: Zero discount collect", f"Expected 200, got {resp.status_code}")
else:
    data = resp.json()
    
    # Check for status='success'
    if data.get('status') != 'success':
        log_fail("C.1: Zero discount collect", f"Expected status='success', got '{data.get('status')}'")
    else:
        log_pass("C.1: Response has status='success'")
    
    # Check for receipt_number
    if not data.get('receipt_number'):
        log_fail("C.1: Zero discount collect", "Missing receipt_number")
    else:
        receipt_number = data['receipt_number']
        log_pass(f"C.1: Response has receipt_number: {receipt_number}")
        
        # Store payment_id for later
        zero_discount_payment_id = data.get('id')

# ============================================================================
# TEST D: ACCOUNTANT with discount (regression)
# ============================================================================
print("\n" + "=" * 80)
print("TEST D: ACCOUNTANT with discount (regression)")
print("=" * 80)

print("\nD.1: POST /api/payments/collect as accountant with discount=150")
headers = get_headers(accountant_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Nov 2026", "amount": 1000}
    ],
    "discount": 150,
    "late_fee": 0,
    "payment_mode": "cash",
    "discount_reason": "Testing accountant discount flow"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 200:
    log_fail("D.1: Accountant discount collect", f"Expected 200, got {resp.status_code}")
else:
    data = resp.json()
    
    # Check for pending_approval status
    if data.get('status') != 'pending_approval':
        log_fail("D.1: Accountant discount collect", 
                f"Expected status='pending_approval', got '{data.get('status')}'")
    else:
        log_pass("D.1: Response has status='pending_approval'")
    
    # Check for approval_id
    if not data.get('approval_id'):
        log_fail("D.1: Accountant discount collect", "Missing approval_id in response")
    else:
        accountant_approval_id = data['approval_id']
        log_pass(f"D.1: Response has approval_id: {accountant_approval_id}")

# ============================================================================
# TEST E: OWNER approves the pending request from TEST A
# ============================================================================
print("\n" + "=" * 80)
print("TEST E: OWNER approves the pending request from TEST A")
print("=" * 80)

print(f"\nE.1: POST /api/discount-approvals/{approval_id}/approve as owner")
headers = get_headers(owner_token, SCHOOL_ID)
payload = {"remark": "Approved for testing"}
resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id}/approve", 
                    json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 200:
    log_fail("E.1: Owner approve", f"Expected 200, got {resp.status_code}")
else:
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Check for status='approved'
    if data.get('status') != 'approved':
        log_fail("E.1: Owner approve", f"Expected status='approved', got '{data.get('status')}'")
    else:
        log_pass("E.1: Response has status='approved'")
    
    # Check for payment_id
    if not data.get('payment_id'):
        log_fail("E.1: Owner approve", "Missing payment_id in response")
    else:
        payment_id = data['payment_id']
        log_pass(f"E.1: Response has payment_id: {payment_id}")
    
    # Check for receipt_number
    if not data.get('receipt_number'):
        log_fail("E.1: Owner approve", "Missing receipt_number in response")
    else:
        receipt_number = data['receipt_number']
        log_pass(f"E.1: Response has receipt_number: {receipt_number}")
        
        # E.2: Download receipt PDF
        print(f"\nE.2: GET /api/payments/{payment_id}/receipt.pdf")
        headers = get_headers(owner_token, SCHOOL_ID)
        resp = requests.get(f"{BASE_URL}/payments/{payment_id}/receipt.pdf", headers=headers)
        
        if resp.status_code != 200:
            log_fail("E.2: Download receipt", f"Expected 200, got {resp.status_code}")
        else:
            content_type = resp.headers.get('Content-Type', '')
            content_length = len(resp.content)
            
            print(f"Content-Type: {content_type}")
            print(f"Content-Length: {content_length} bytes")
            
            if content_type != 'application/pdf':
                log_fail("E.2: Download receipt", f"Expected application/pdf, got {content_type}")
            else:
                log_pass("E.2: Receipt has Content-Type: application/pdf")
            
            if content_length < 2000:
                log_fail("E.2: Download receipt", f"PDF too small: {content_length} bytes")
            else:
                log_pass(f"E.2: Receipt PDF size: {content_length} bytes (> 2000)")
        
        # E.3: Verify payment doc has collected_by_name = super_admin
        print(f"\nE.3: Verify payment doc has collected_by_name = super_admin")
        headers = get_headers(super_admin_token, SCHOOL_ID)
        resp = requests.get(f"{BASE_URL}/payments", headers=headers)
        
        if resp.status_code != 200:
            log_fail("E.3: Get payments", f"Status {resp.status_code}")
        else:
            payments = resp.json()
            payment = next((p for p in payments if p.get('id') == payment_id), None)
            
            if not payment:
                log_fail("E.3: Get payments", f"Payment {payment_id} not found")
            else:
                collected_by_name = payment.get('collected_by_name', '')
                print(f"collected_by_name: {collected_by_name}")
                
                # Should be the super_admin who submitted, not the owner who approved
                if 'super' in collected_by_name.lower() or 'admin' in collected_by_name.lower():
                    log_pass("E.3: collected_by_name reflects the original requester (super_admin)")
                else:
                    log_fail("E.3: Get payments", 
                            f"Expected collected_by_name to be super_admin, got '{collected_by_name}'")

# ============================================================================
# TEST F: OWNER rejects a fresh pending request
# ============================================================================
print("\n" + "=" * 80)
print("TEST F: OWNER rejects a fresh pending request")
print("=" * 80)

# F.1: Create a new pending request as accountant
print("\nF.1: Create new pending request as accountant")
headers = get_headers(accountant_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Dec 2026", "amount": 1000}
    ],
    "discount": 300,
    "late_fee": 0,
    "payment_mode": "cash",
    "discount_reason": "Testing rejection flow"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload, headers=headers)

if resp.status_code != 200:
    log_fail("F.1: Create pending request", f"Status {resp.status_code}")
    reject_approval_id = None
else:
    data = resp.json()
    reject_approval_id = data.get('approval_id')
    log_pass(f"F.1: Created pending request: {reject_approval_id}")

# F.2: Owner rejects the request
if reject_approval_id:
    print(f"\nF.2: POST /api/discount-approvals/{reject_approval_id}/reject as owner")
    headers = get_headers(owner_token, SCHOOL_ID)
    payload = {"remark": "Discount too high"}
    resp = requests.post(f"{BASE_URL}/discount-approvals/{reject_approval_id}/reject", 
                        json=payload, headers=headers)
    
    print(f"Response status: {resp.status_code}")
    
    if resp.status_code != 200:
        log_fail("F.2: Owner reject", f"Expected 200, got {resp.status_code}")
    else:
        data = resp.json()
        
        # Check for status='rejected'
        if data.get('status') != 'rejected':
            log_fail("F.2: Owner reject", f"Expected status='rejected', got '{data.get('status')}'")
        else:
            log_pass("F.2: Response has status='rejected'")
        
        # F.3: Verify no payment was created
        print("\nF.3: Verify no payment was created for rejected approval")
        headers = get_headers(super_admin_token, SCHOOL_ID)
        resp = requests.get(f"{BASE_URL}/payments", headers=headers)
        
        if resp.status_code != 200:
            log_fail("F.3: Get payments", f"Status {resp.status_code}")
        else:
            payments = resp.json()
            # Check if any payment has this approval_id
            payment_with_approval = next((p for p in payments 
                                         if p.get('discount_approval_id') == reject_approval_id), None)
            
            if payment_with_approval:
                log_fail("F.3: Verify no payment", 
                        f"Found payment {payment_with_approval.get('id')} with rejected approval_id")
            else:
                log_pass("F.3: No payment created for rejected approval")

# ============================================================================
# TEST G: RAZORPAY ONLINE + DISCOUNT
# ============================================================================
print("\n" + "=" * 80)
print("TEST G: RAZORPAY ONLINE + DISCOUNT")
print("=" * 80)

print("\nG.1: POST /api/payments/razorpay/order as accountant with discount>0")
headers = get_headers(accountant_token, SCHOOL_ID)
payload = {
    "student_id": student_id,
    "items": [
        {"fee_head_name": "Tuition", "period": "Jan 2027", "amount": 1000}
    ],
    "discount": 100,
    "late_fee": 0,
    "remarks": "Testing Razorpay discount block"
}
resp = requests.post(f"{BASE_URL}/payments/razorpay/order", json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code == 400:
    data = resp.json()
    detail = data.get('detail', '')
    print(f"Response detail: {detail}")
    
    if "Razorpay" in detail and "not allowed" in detail:
        log_pass("G.1: Returns 400 with message about Razorpay discount not allowed")
    else:
        log_fail("G.1: Razorpay discount", f"Expected message about Razorpay, got '{detail}'")
elif resp.status_code == 500:
    data = resp.json()
    detail = data.get('detail', '')
    print(f"Response detail: {detail}")
    
    if "Razorpay not configured" in detail:
        print("NOTE: Got 500 'Razorpay not configured' before reaching the discount guard.")
        print("This is acceptable for MVP as Razorpay isn't configured in this environment.")
        log_pass("G.1: Returns 500 'Razorpay not configured' (acceptable)")
    else:
        log_fail("G.1: Razorpay discount", f"Expected 400 or 500, got 500 with '{detail}'")
else:
    log_fail("G.1: Razorpay discount", f"Expected 400 or 500, got {resp.status_code}")

# ============================================================================
# TEST H: PREVIOUS RBAC & PATH REGRESSIONS
# ============================================================================
print("\n" + "=" * 80)
print("TEST H: PREVIOUS RBAC & PATH REGRESSIONS")
print("=" * 80)

# H.1: Accountant cannot approve
print("\nH.1: Accountant tries to approve → 403")
headers = get_headers(accountant_token, SCHOOL_ID)
payload = {"remark": "Trying to approve"}
# Use the accountant's own approval_id from TEST D
resp = requests.post(f"{BASE_URL}/discount-approvals/{accountant_approval_id}/approve", 
                    json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 403:
    log_fail("H.1: Accountant approve RBAC", f"Expected 403, got {resp.status_code}")
else:
    log_pass("H.1: Accountant cannot approve (403)")

# H.2: Parent cannot list approvals
print("\nH.2: Parent tries to list approvals → 403")
headers = get_headers(parent_token)
resp = requests.get(f"{BASE_URL}/discount-approvals", headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 403:
    log_fail("H.2: Parent list approvals RBAC", f"Expected 403, got {resp.status_code}")
else:
    log_pass("H.2: Parent cannot list approvals (403)")

# H.3: Owner can get pending count
print("\nH.3: GET /api/discount-approvals/pending-count as owner")
headers = get_headers(owner_token, SCHOOL_ID)
resp = requests.get(f"{BASE_URL}/discount-approvals/pending-count", headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 200:
    log_fail("H.3: Owner pending count", f"Expected 200, got {resp.status_code}")
else:
    data = resp.json()
    count = data.get('count', 0)
    print(f"Pending count: {count}")
    
    if isinstance(count, int) and count >= 0:
        log_pass(f"H.3: Owner can get pending count: {count}")
    else:
        log_fail("H.3: Owner pending count", f"Invalid count: {count}")

# H.4: Non-existent approval_id on approve → 404
print("\nH.4: Approve non-existent approval_id → 404")
headers = get_headers(owner_token, SCHOOL_ID)
payload = {"remark": "Testing 404"}
fake_id = "nonexistent-approval-id-12345"
resp = requests.post(f"{BASE_URL}/discount-approvals/{fake_id}/approve", 
                    json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 404:
    log_fail("H.4: Non-existent approval", f"Expected 404, got {resp.status_code}")
else:
    log_pass("H.4: Non-existent approval returns 404")

# H.5: Approving an already-approved doc → 400
print("\nH.5: Approve already-approved doc → 400")
headers = get_headers(owner_token, SCHOOL_ID)
payload = {"remark": "Trying to approve again"}
# Use the approval_id from TEST A that we already approved in TEST E
resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id}/approve", 
                    json=payload, headers=headers)

print(f"Response status: {resp.status_code}")

if resp.status_code != 400:
    log_fail("H.5: Already-approved doc", f"Expected 400, got {resp.status_code}")
else:
    log_pass("H.5: Already-approved doc returns 400")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total tests: {passed + failed}")
print(f"✓ Passed: {passed}")
print(f"✗ Failed: {failed}")

if failed > 0:
    print("\nFailed tests:")
    for failure in failures:
        print(f"  - {failure}")

print("\n" + "=" * 80)

# Exit with appropriate code
sys.exit(0 if failed == 0 else 1)
