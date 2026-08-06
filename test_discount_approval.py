#!/usr/bin/env python3
"""
Comprehensive test for Discount Approval workflow in Stanvard School ERP.
Tests POST /api/payments/collect with discount approval, approval endpoints, and owner RBAC.
"""
import requests
import json
import sys
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://code-standard-1.preview.emergentagent.com/api"

# Test credentials
OWNER_SATYA = {"email": "satya.mundra@stanvard.school", "password": "Mundra@Satya2026"}
OWNER_MRITYUNJAY = {"email": "mrityunjay.mundra@stanvard.school", "password": "Mundra@Mrityunjay2026"}
ACCOUNTANT = {"email": "accountant@stanvard.school", "password": "Accountant@2026"}
SUPER_ADMIN = {"email": "superadmin@stanvard.school", "password": "Stanvard@2026"}
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
        log_fail(f"Login {credentials.get('email', credentials.get('mobile'))}", f"Status {resp.status_code}")
        return None
    data = resp.json()
    return data.get('access_token')

def get_headers(token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {token}"}

def get_student_id(token):
    """Get a valid student ID for testing."""
    resp = requests.get(f"{BASE_URL}/students?limit=1", headers=get_headers(token))
    if resp.status_code == 200:
        students = resp.json()
        if students and len(students) > 0:
            return students[0]['id']
    return None

print("=" * 80)
print("DISCOUNT APPROVAL WORKFLOW TESTING")
print("=" * 80)

# ============================================================================
# TEST 1: POST /api/payments/collect - Discount Approval Flow
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: POST /api/payments/collect - Discount Approval Flow")
print("=" * 80)

# Login as accountant
accountant_token = login(ACCOUNTANT)
if not accountant_token:
    print("❌ Failed to login as accountant. Aborting tests.")
    sys.exit(1)
log_pass("Login as accountant")

# Get a valid student ID
student_id = get_student_id(accountant_token)
if not student_id:
    print("❌ Failed to get student ID. Aborting tests.")
    sys.exit(1)
log_pass(f"Got student ID: {student_id}")

# Test 1a: discount=0 (no discount) → should return 200 with payment status='success'
print("\n--- Test 1a: No discount payment ---")
payload_no_discount = {
    "student_id": student_id,
    "items": [{"fee_head_id": "test-head", "fee_head_name": "Test Fee", "amount": 500, "period": "Test"}],
    "discount": 0,
    "late_fee": 0,
    "payment_mode": "cash",
    "remarks": "Test payment no discount"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload_no_discount, headers=get_headers(accountant_token))
if resp.status_code == 200:
    data = resp.json()
    if data.get('status') == 'success' and data.get('receipt_number'):
        log_pass("1a: No discount payment returns 200 with status='success' and receipt_number")
        payment_no_discount_id = data.get('id')
    else:
        log_fail("1a: No discount payment", f"Missing status='success' or receipt_number. Got: {data}")
else:
    log_fail("1a: No discount payment", f"Status {resp.status_code}: {resp.text}")

# Test 1b: discount>0 without discount_reason → should return 400
print("\n--- Test 1b: Discount without reason ---")
payload_discount_no_reason = {
    "student_id": student_id,
    "items": [{"fee_head_id": "test-head", "fee_head_name": "Test Fee", "amount": 500, "period": "Test"}],
    "discount": 100,
    "late_fee": 0,
    "payment_mode": "cash",
    "remarks": "Test payment with discount but no reason"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload_discount_no_reason, headers=get_headers(accountant_token))
if resp.status_code == 400:
    data = resp.json()
    if 'discount reason' in data.get('detail', '').lower():
        log_pass("1b: Discount without reason returns 400 with 'Discount reason is required' message")
    else:
        log_fail("1b: Discount without reason", f"400 but wrong message: {data.get('detail')}")
else:
    log_fail("1b: Discount without reason", f"Expected 400, got {resp.status_code}: {resp.text}")

# Test 1c: discount>0 with discount_reason → should return 200 with status='pending_approval'
print("\n--- Test 1c: Discount with reason (accountant) ---")
payload_discount_with_reason = {
    "student_id": student_id,
    "items": [{"fee_head_id": "test-head", "fee_head_name": "Test Fee", "amount": 500, "period": "Test"}],
    "discount": 100,
    "discount_reason": "Sibling discount",
    "late_fee": 0,
    "payment_mode": "cash",
    "remarks": "Test payment with discount and reason"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload_discount_with_reason, headers=get_headers(accountant_token))
if resp.status_code == 200:
    data = resp.json()
    if data.get('status') == 'pending_approval' and data.get('approval_id') and data.get('approval'):
        log_pass("1c: Discount with reason returns 200 with status='pending_approval' and approval_id")
        approval_id_1c = data.get('approval_id')
        # Verify NO payment document created yet
        resp_payments = requests.get(f"{BASE_URL}/payments", headers=get_headers(accountant_token))
        if resp_payments.status_code == 200:
            payments = resp_payments.json()
            # Check if any payment has this approval_id (should not exist yet)
            pending_payment = next((p for p in payments if p.get('discount_approval_id') == approval_id_1c), None)
            if not pending_payment:
                log_pass("1c: No payment document created yet (verified)")
            else:
                log_fail("1c: Payment verification", f"Payment document found with approval_id {approval_id_1c}, should not exist yet")
        else:
            log_fail("1c: Payment verification", f"Failed to fetch payments: {resp_payments.status_code}")
    else:
        log_fail("1c: Discount with reason", f"Missing status='pending_approval' or approval_id. Got: {data}")
else:
    log_fail("1c: Discount with reason", f"Status {resp.status_code}: {resp.text}")

# Test 1d: discount>0 with super_admin → should bypass approval
print("\n--- Test 1d: Discount with super_admin (bypass approval) ---")
super_admin_token = login(SUPER_ADMIN)
if not super_admin_token:
    log_fail("1d: Super admin login", "Failed to login")
else:
    log_pass("Login as super_admin")
    payload_super_admin_discount = {
        "student_id": student_id,
        "items": [{"fee_head_id": "test-head", "fee_head_name": "Test Fee", "amount": 500, "period": "Test"}],
        "discount": 100,
        "discount_reason": "Super admin discount",
        "late_fee": 0,
        "payment_mode": "cash",
        "remarks": "Test super admin discount bypass"
    }
    resp = requests.post(f"{BASE_URL}/payments/collect", json=payload_super_admin_discount, headers=get_headers(super_admin_token))
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'success' and data.get('receipt_number'):
            log_pass("1d: Super admin discount bypasses approval and returns payment immediately")
        else:
            log_fail("1d: Super admin discount", f"Expected status='success' and receipt_number. Got: {data}")
    else:
        log_fail("1d: Super admin discount", f"Status {resp.status_code}: {resp.text}")

# ============================================================================
# TEST 2: GET /api/discount-approvals - List and Filter
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: GET /api/discount-approvals - List and Filter")
print("=" * 80)

# Login as owner
owner_token = login(OWNER_SATYA)
if not owner_token:
    print("❌ Failed to login as owner. Aborting tests.")
    sys.exit(1)
log_pass("Login as owner (Satya)")

# Test 2a: Owner without query param → should return all approvals
print("\n--- Test 2a: Owner list all approvals ---")
resp = requests.get(f"{BASE_URL}/discount-approvals", headers=get_headers(owner_token))
if resp.status_code == 200:
    approvals = resp.json()
    if isinstance(approvals, list):
        log_pass(f"2a: Owner can list all approvals (found {len(approvals)} approvals)")
        # Check if our pending approval from 1c is in the list
        if 'approval_id_1c' in locals():
            found = next((a for a in approvals if a.get('id') == approval_id_1c), None)
            if found:
                log_pass("2a: Pending approval from test 1c found in list")
            else:
                log_fail("2a: Pending approval verification", f"Approval {approval_id_1c} not found in list")
    else:
        log_fail("2a: Owner list approvals", f"Expected list, got: {type(approvals)}")
else:
    log_fail("2a: Owner list approvals", f"Status {resp.status_code}: {resp.text}")

# Test 2b: Owner with ?status=pending
print("\n--- Test 2b: Owner list pending approvals ---")
resp = requests.get(f"{BASE_URL}/discount-approvals?status=pending", headers=get_headers(owner_token))
if resp.status_code == 200:
    approvals = resp.json()
    if isinstance(approvals, list):
        all_pending = all(a.get('status') == 'pending' for a in approvals)
        if all_pending:
            log_pass(f"2b: Owner can filter by status=pending (found {len(approvals)} pending)")
        else:
            log_fail("2b: Owner filter pending", "Some approvals are not pending")
    else:
        log_fail("2b: Owner filter pending", f"Expected list, got: {type(approvals)}")
else:
    log_fail("2b: Owner filter pending", f"Status {resp.status_code}: {resp.text}")

# Test 2c: Owner with ?status=approved
print("\n--- Test 2c: Owner list approved approvals ---")
resp = requests.get(f"{BASE_URL}/discount-approvals?status=approved", headers=get_headers(owner_token))
if resp.status_code == 200:
    approvals = resp.json()
    if isinstance(approvals, list):
        all_approved = all(a.get('status') == 'approved' for a in approvals)
        if all_approved or len(approvals) == 0:
            log_pass(f"2c: Owner can filter by status=approved (found {len(approvals)} approved)")
        else:
            log_fail("2c: Owner filter approved", "Some approvals are not approved")
    else:
        log_fail("2c: Owner filter approved", f"Expected list, got: {type(approvals)}")
else:
    log_fail("2c: Owner filter approved", f"Status {resp.status_code}: {resp.text}")

# Test 2d: Owner with ?status=rejected
print("\n--- Test 2d: Owner list rejected approvals ---")
resp = requests.get(f"{BASE_URL}/discount-approvals?status=rejected", headers=get_headers(owner_token))
if resp.status_code == 200:
    approvals = resp.json()
    if isinstance(approvals, list):
        all_rejected = all(a.get('status') == 'rejected' for a in approvals)
        if all_rejected or len(approvals) == 0:
            log_pass(f"2d: Owner can filter by status=rejected (found {len(approvals)} rejected)")
        else:
            log_fail("2d: Owner filter rejected", "Some approvals are not rejected")
    else:
        log_fail("2d: Owner filter rejected", f"Expected list, got: {type(approvals)}")
else:
    log_fail("2d: Owner filter rejected", f"Status {resp.status_code}: {resp.text}")

# Test 2e: Accountant → should only see their own submissions
print("\n--- Test 2e: Accountant list approvals (own only) ---")
resp = requests.get(f"{BASE_URL}/discount-approvals", headers=get_headers(accountant_token))
if resp.status_code == 200:
    approvals = resp.json()
    if isinstance(approvals, list):
        log_pass(f"2e: Accountant can list approvals (found {len(approvals)} approvals)")
        # All should be requested by this accountant
        # We can't verify the exact user ID without fetching /auth/me, but we can check structure
    else:
        log_fail("2e: Accountant list approvals", f"Expected list, got: {type(approvals)}")
else:
    log_fail("2e: Accountant list approvals", f"Status {resp.status_code}: {resp.text}")

# Test 2f: Parent → should return 403
print("\n--- Test 2f: Parent list approvals (should be 403) ---")
parent_token = login(PARENT)
if parent_token:
    resp = requests.get(f"{BASE_URL}/discount-approvals", headers=get_headers(parent_token))
    if resp.status_code == 403:
        log_pass("2f: Parent access to discount-approvals returns 403")
    else:
        log_fail("2f: Parent access", f"Expected 403, got {resp.status_code}: {resp.text}")
else:
    log_fail("2f: Parent login", "Failed to login as parent")

# Test 2g: GET /api/discount-approvals/pending-count
print("\n--- Test 2g: Pending count endpoint ---")
resp = requests.get(f"{BASE_URL}/discount-approvals/pending-count", headers=get_headers(owner_token))
if resp.status_code == 200:
    data = resp.json()
    if 'count' in data and isinstance(data['count'], int):
        log_pass(f"2g: Pending count endpoint returns count: {data['count']}")
    else:
        log_fail("2g: Pending count", f"Expected 'count' field, got: {data}")
else:
    log_fail("2g: Pending count", f"Status {resp.status_code}: {resp.text}")

# ============================================================================
# TEST 3: GET /api/discount-approvals/{id} - RBAC
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: GET /api/discount-approvals/{id} - RBAC")
print("=" * 80)

if 'approval_id_1c' in locals():
    # Test 3a: Owner can see any approval
    print("\n--- Test 3a: Owner get approval by ID ---")
    resp = requests.get(f"{BASE_URL}/discount-approvals/{approval_id_1c}", headers=get_headers(owner_token))
    if resp.status_code == 200:
        data = resp.json()
        if data.get('id') == approval_id_1c:
            log_pass("3a: Owner can get approval by ID")
        else:
            log_fail("3a: Owner get approval", f"ID mismatch: expected {approval_id_1c}, got {data.get('id')}")
    else:
        log_fail("3a: Owner get approval", f"Status {resp.status_code}: {resp.text}")

    # Test 3b: Accountant can see own approval
    print("\n--- Test 3b: Accountant get own approval by ID ---")
    resp = requests.get(f"{BASE_URL}/discount-approvals/{approval_id_1c}", headers=get_headers(accountant_token))
    if resp.status_code == 200:
        data = resp.json()
        if data.get('id') == approval_id_1c:
            log_pass("3b: Accountant can get own approval by ID")
        else:
            log_fail("3b: Accountant get approval", f"ID mismatch: expected {approval_id_1c}, got {data.get('id')}")
    else:
        log_fail("3b: Accountant get approval", f"Status {resp.status_code}: {resp.text}")

    # Test 3c: Parent → should return 403
    print("\n--- Test 3c: Parent get approval by ID (should be 403) ---")
    if parent_token:
        resp = requests.get(f"{BASE_URL}/discount-approvals/{approval_id_1c}", headers=get_headers(parent_token))
        if resp.status_code == 403:
            log_pass("3c: Parent access to approval by ID returns 403")
        else:
            log_fail("3c: Parent access", f"Expected 403, got {resp.status_code}: {resp.text}")
else:
    log_fail("TEST 3", "No approval_id_1c available from test 1c")

# ============================================================================
# TEST 4: POST /api/discount-approvals/{id}/approve
# ============================================================================
print("\n" + "=" * 80)
print("TEST 4: POST /api/discount-approvals/{id}/approve")
print("=" * 80)

if 'approval_id_1c' in locals():
    # Test 4a: Accountant cannot approve → should return 403
    print("\n--- Test 4a: Accountant approve (should be 403) ---")
    resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id_1c}/approve", 
                         json={"remark": "Test approval"}, 
                         headers=get_headers(accountant_token))
    if resp.status_code == 403:
        log_pass("4a: Accountant cannot approve (403)")
    else:
        log_fail("4a: Accountant approve", f"Expected 403, got {resp.status_code}: {resp.text}")

    # Test 4b: Owner can approve → should return 200 with payment details
    print("\n--- Test 4b: Owner approve pending approval ---")
    resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id_1c}/approve", 
                         json={"remark": "Approved by owner"}, 
                         headers=get_headers(owner_token))
    if resp.status_code == 200:
        data = resp.json()
        if data.get('ok') and data.get('status') == 'approved' and data.get('payment_id') and data.get('receipt_number'):
            log_pass("4b: Owner approve returns 200 with ok=True, status='approved', payment_id, receipt_number")
            payment_id_4b = data.get('payment_id')
            receipt_number_4b = data.get('receipt_number')
            
            # Verify the DiscountApproval doc is updated
            print("\n--- Test 4c: Verify DiscountApproval doc updated ---")
            resp_approval = requests.get(f"{BASE_URL}/discount-approvals/{approval_id_1c}", headers=get_headers(owner_token))
            if resp_approval.status_code == 200:
                approval_doc = resp_approval.json()
                checks = []
                checks.append(('status', approval_doc.get('status') == 'approved'))
                checks.append(('reviewed_by_name', approval_doc.get('reviewed_by_name') is not None))
                checks.append(('reviewed_at', approval_doc.get('reviewed_at') is not None))
                checks.append(('payment_id', approval_doc.get('payment_id') == payment_id_4b))
                checks.append(('receipt_number', approval_doc.get('receipt_number') == receipt_number_4b))
                
                all_passed = all(check[1] for check in checks)
                if all_passed:
                    log_pass("4c: DiscountApproval doc updated correctly (status, reviewed_by_name, reviewed_at, payment_id, receipt_number)")
                else:
                    failed_checks = [check[0] for check in checks if not check[1]]
                    log_fail("4c: DiscountApproval doc", f"Failed checks: {', '.join(failed_checks)}")
            else:
                log_fail("4c: DiscountApproval doc", f"Failed to fetch approval: {resp_approval.status_code}")
            
            # Verify the Payment doc is created
            print("\n--- Test 4d: Verify Payment doc created ---")
            resp_payment = requests.get(f"{BASE_URL}/payments", headers=get_headers(owner_token))
            if resp_payment.status_code == 200:
                payments = resp_payment.json()
                payment_doc = next((p for p in payments if p.get('id') == payment_id_4b), None)
                if payment_doc:
                    checks = []
                    checks.append(('status', payment_doc.get('status') == 'success'))
                    checks.append(('discount', payment_doc.get('discount') == 100))
                    checks.append(('discount_approval_id', payment_doc.get('discount_approval_id') == approval_id_1c))
                    checks.append(('discount_reason', payment_doc.get('discount_reason') == 'Sibling discount'))
                    checks.append(('discount_approved_by_id', payment_doc.get('discount_approved_by_id') is not None))
                    checks.append(('discount_approved_by_name', payment_doc.get('discount_approved_by_name') is not None))
                    
                    # CRITICAL: collected_by_name should reflect the ORIGINAL requester (accountant), not the owner
                    collected_by_name = payment_doc.get('collected_by_name', '')
                    # The accountant's name should be in collected_by_name
                    # We expect it to NOT be the owner's name
                    owner_name_in_collected = 'satya' in collected_by_name.lower() or 'mundra' in collected_by_name.lower()
                    if not owner_name_in_collected:
                        checks.append(('collected_by_name_is_accountant', True))
                        log_pass("4d: collected_by_name reflects the original requester (accountant), not the owner")
                    else:
                        checks.append(('collected_by_name_is_accountant', False))
                        log_fail("4d: collected_by_name", f"Expected accountant name, got: {collected_by_name}")
                    
                    all_passed = all(check[1] for check in checks)
                    if all_passed:
                        log_pass("4d: Payment doc created with correct fields (status, discount, discount_approval_id, discount_reason, discount_approved_by_*)")
                    else:
                        failed_checks = [check[0] for check in checks if not check[1]]
                        log_fail("4d: Payment doc", f"Failed checks: {', '.join(failed_checks)}")
                else:
                    log_fail("4d: Payment doc", f"Payment {payment_id_4b} not found")
            else:
                log_fail("4d: Payment doc", f"Failed to fetch payments: {resp_payment.status_code}")
            
            # Verify receipt PDF is generated
            print("\n--- Test 4e: Verify receipt PDF ---")
            resp_pdf = requests.get(f"{BASE_URL}/payments/{payment_id_4b}/receipt.pdf", headers=get_headers(owner_token))
            if resp_pdf.status_code == 200:
                content_type = resp_pdf.headers.get('Content-Type', '')
                content_length = len(resp_pdf.content)
                pdf_signature = resp_pdf.content[:5] == b'%PDF-'
                
                if content_type == 'application/pdf' and content_length > 2000 and pdf_signature:
                    log_pass(f"4e: Receipt PDF generated correctly (application/pdf, {content_length} bytes, valid PDF signature)")
                else:
                    log_fail("4e: Receipt PDF", f"Invalid PDF: content_type={content_type}, size={content_length}, signature={pdf_signature}")
            else:
                log_fail("4e: Receipt PDF", f"Status {resp_pdf.status_code}: {resp_pdf.text}")
        else:
            log_fail("4b: Owner approve", f"Missing required fields. Got: {data}")
    else:
        log_fail("4b: Owner approve", f"Status {resp.status_code}: {resp.text}")

    # Test 4f: Approving already-approved doc → should return 400
    print("\n--- Test 4f: Approve already-approved doc (should be 400) ---")
    resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id_1c}/approve", 
                         json={"remark": "Try to approve again"}, 
                         headers=get_headers(owner_token))
    if resp.status_code == 400:
        log_pass("4f: Approving already-approved doc returns 400")
    else:
        log_fail("4f: Approve already-approved", f"Expected 400, got {resp.status_code}: {resp.text}")
else:
    log_fail("TEST 4", "No approval_id_1c available from test 1c")

# ============================================================================
# TEST 5: POST /api/discount-approvals/{id}/reject
# ============================================================================
print("\n" + "=" * 80)
print("TEST 5: POST /api/discount-approvals/{id}/reject")
print("=" * 80)

# Create a new pending approval for rejection test
print("\n--- Test 5a: Create new pending approval for rejection ---")
payload_for_rejection = {
    "student_id": student_id,
    "items": [{"fee_head_id": "test-head", "fee_head_name": "Test Fee", "amount": 500, "period": "Test"}],
    "discount": 150,
    "discount_reason": "Test rejection scenario",
    "late_fee": 0,
    "payment_mode": "cash",
    "remarks": "Test payment for rejection"
}
resp = requests.post(f"{BASE_URL}/payments/collect", json=payload_for_rejection, headers=get_headers(accountant_token))
if resp.status_code == 200:
    data = resp.json()
    if data.get('status') == 'pending_approval' and data.get('approval_id'):
        approval_id_5a = data.get('approval_id')
        log_pass(f"5a: Created new pending approval for rejection: {approval_id_5a}")
        
        # Test 5b: Owner reject with remark
        print("\n--- Test 5b: Owner reject pending approval ---")
        resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id_5a}/reject", 
                             json={"remark": "Discount too high"}, 
                             headers=get_headers(owner_token))
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok') and data.get('status') == 'rejected':
                log_pass("5b: Owner reject returns 200 with ok=True, status='rejected'")
                
                # Verify the DiscountApproval doc is updated
                print("\n--- Test 5c: Verify DiscountApproval doc updated after rejection ---")
                resp_approval = requests.get(f"{BASE_URL}/discount-approvals/{approval_id_5a}", headers=get_headers(owner_token))
                if resp_approval.status_code == 200:
                    approval_doc = resp_approval.json()
                    checks = []
                    checks.append(('status', approval_doc.get('status') == 'rejected'))
                    checks.append(('reviewed_by_name', approval_doc.get('reviewed_by_name') is not None))
                    checks.append(('reviewed_at', approval_doc.get('reviewed_at') is not None))
                    checks.append(('review_remark', approval_doc.get('review_remark') == 'Discount too high'))
                    
                    all_passed = all(check[1] for check in checks)
                    if all_passed:
                        log_pass("5c: DiscountApproval doc updated correctly after rejection")
                    else:
                        failed_checks = [check[0] for check in checks if not check[1]]
                        log_fail("5c: DiscountApproval doc", f"Failed checks: {', '.join(failed_checks)}")
                else:
                    log_fail("5c: DiscountApproval doc", f"Failed to fetch approval: {resp_approval.status_code}")
                
                # Verify NO payment is created
                print("\n--- Test 5d: Verify NO payment created after rejection ---")
                resp_payment = requests.get(f"{BASE_URL}/payments", headers=get_headers(owner_token))
                if resp_payment.status_code == 200:
                    payments = resp_payment.json()
                    payment_doc = next((p for p in payments if p.get('discount_approval_id') == approval_id_5a), None)
                    if not payment_doc:
                        log_pass("5d: No payment created after rejection (verified)")
                    else:
                        log_fail("5d: Payment verification", f"Payment found with approval_id {approval_id_5a}, should not exist")
                else:
                    log_fail("5d: Payment verification", f"Failed to fetch payments: {resp_payment.status_code}")
            else:
                log_fail("5b: Owner reject", f"Missing required fields. Got: {data}")
        else:
            log_fail("5b: Owner reject", f"Status {resp.status_code}: {resp.text}")
        
        # Test 5e: Rejecting already-rejected doc → should return 400
        print("\n--- Test 5e: Reject already-rejected doc (should be 400) ---")
        resp = requests.post(f"{BASE_URL}/discount-approvals/{approval_id_5a}/reject", 
                             json={"remark": "Try to reject again"}, 
                             headers=get_headers(owner_token))
        if resp.status_code == 400:
            log_pass("5e: Rejecting already-rejected doc returns 400")
        else:
            log_fail("5e: Reject already-rejected", f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_fail("5a: Create pending approval", f"Missing status='pending_approval' or approval_id. Got: {data}")
else:
    log_fail("5a: Create pending approval", f"Status {resp.status_code}: {resp.text}")

# ============================================================================
# TEST 6: Owner READ RBAC
# ============================================================================
print("\n" + "=" * 80)
print("TEST 6: Owner READ RBAC")
print("=" * 80)

owner_rbac_endpoints = [
    ('/auth/my-schools', 'my-schools'),
    ('/dashboard/summary', 'dashboard/summary'),
    ('/users', 'users'),
    ('/analytics', 'analytics'),
    ('/analytics/fees', 'analytics/fees'),
    ('/reports/collection?start=2026-01-01&end=2026-12-31', 'reports/collection'),
    ('/reports/fee-status', 'reports/fee-status'),
    ('/schools', 'schools'),
]

for endpoint, name in owner_rbac_endpoints:
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=get_headers(owner_token))
    if resp.status_code == 200:
        log_pass(f"6: Owner can access {name} (200)")
    else:
        log_fail(f"6: Owner access {name}", f"Expected 200, got {resp.status_code}: {resp.text}")

# Verify owner is scoped to KNP school
print("\n--- Test 6x: Verify owner is scoped to KNP school ---")
resp = requests.get(f"{BASE_URL}/auth/my-schools", headers=get_headers(owner_token))
if resp.status_code == 200:
    schools = resp.json()
    if isinstance(schools, list) and len(schools) > 0:
        school_codes = [s.get('code', '') for s in schools]
        if 'KNP' in school_codes:
            log_pass("6x: Owner is scoped to KNP school")
        else:
            log_fail("6x: Owner school scope", f"Expected KNP, got: {school_codes}")
    else:
        log_fail("6x: Owner school scope", f"No schools returned: {schools}")
else:
    log_fail("6x: Owner school scope", f"Failed to fetch schools: {resp.status_code}")

# ============================================================================
# TEST 7: Regression - Earlier Features
# ============================================================================
print("\n" + "=" * 80)
print("TEST 7: Regression - Earlier Features (Quick Smoke Test)")
print("=" * 80)

# Test fee heads CRUD
print("\n--- Test 7a: Fee heads CRUD ---")
resp = requests.get(f"{BASE_URL}/fees/heads", headers=get_headers(super_admin_token))
if resp.status_code == 200:
    log_pass("7a: GET /api/fees/heads works")
else:
    log_fail("7a: Fee heads", f"Status {resp.status_code}")

# Test fee plans CRUD
print("\n--- Test 7b: Fee plans CRUD ---")
resp = requests.get(f"{BASE_URL}/fees/plans", headers=get_headers(super_admin_token))
if resp.status_code == 200:
    log_pass("7b: GET /api/fees/plans works")
else:
    log_fail("7b: Fee plans", f"Status {resp.status_code}")

# Test fee-schedule endpoint
print("\n--- Test 7c: Fee schedule endpoint ---")
resp = requests.get(f"{BASE_URL}/fees/student/{student_id}/fee-schedule", headers=get_headers(super_admin_token))
if resp.status_code == 200:
    data = resp.json()
    if 'schedule' in data and len(data['schedule']) == 12:
        log_pass("7c: GET /api/fees/student/{id}/fee-schedule works (12 months)")
    else:
        log_fail("7c: Fee schedule", f"Expected 12 months, got: {len(data.get('schedule', []))}")
else:
    log_fail("7c: Fee schedule", f"Status {resp.status_code}")

# Test receipt PDF for existing payment
if 'payment_no_discount_id' in locals():
    print("\n--- Test 7d: Receipt PDF for existing payment ---")
    resp = requests.get(f"{BASE_URL}/payments/{payment_no_discount_id}/receipt.pdf", headers=get_headers(accountant_token))
    if resp.status_code == 200:
        content_type = resp.headers.get('Content-Type', '')
        if content_type == 'application/pdf':
            log_pass("7d: Receipt PDF for existing payment works")
        else:
            log_fail("7d: Receipt PDF", f"Wrong content type: {content_type}")
    else:
        log_fail("7d: Receipt PDF", f"Status {resp.status_code}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total tests: {passed + failed}")
print(f"✓ Passed: {passed}")
print(f"✗ Failed: {failed}")
print(f"Success rate: {passed / (passed + failed) * 100:.1f}%")

if failed > 0:
    print("\n" + "=" * 80)
    print("FAILURES:")
    print("=" * 80)
    for failure in failures:
        print(f"  ✗ {failure}")

print("\n" + "=" * 80)
sys.exit(0 if failed == 0 else 1)
