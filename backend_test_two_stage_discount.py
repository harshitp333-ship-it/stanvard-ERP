#!/usr/bin/env python3
"""
Test script for TWO-STAGE DISCOUNT APPROVAL WORKFLOW (Jul 2026 update)
Tests the new workflow where:
1. Admin submits discount request with application_image → pending_approval
2. Owner approves (optionally editing discount) → approved (NO payment yet)
3. Admin collects payment → collected (payment + receipt generated)
"""
import requests
import json
import os
from datetime import datetime

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://2858fe9c-e532-4876-9987-caf4614bddb4.preview.emergentagent.com')
API_URL = f"{BASE_URL}/api"

# Test credentials
SUPER_ADMIN = {"email": "superadmin@stanvard.school", "password": "Stanvard@2026"}
ACCOUNTANT = {"email": "accountant@stanvard.school", "password": "Accountant@2026"}
OWNER = {"email": "satya.mundra@stanvard.school", "password": "Mundra@Satya2026"}

# KNP School ID
SCHOOL_ID = "034cab3a-3107-4cf2-bfdb-3bba434a5367"

# Tiny valid PNG base64 for testing
TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII="

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✓ PASS"
    else:
        tests_failed += 1
        status = "✗ FAIL"
    result = f"{status}: {name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)

def login(credentials):
    """Login and return token + user info"""
    resp = requests.post(f"{API_URL}/auth/login", json=credentials)
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return data['access_token'], data['user']

def get_headers(token, school_id=None):
    """Build request headers"""
    headers = {"Authorization": f"Bearer {token}"}
    if school_id:
        headers["X-School-Id"] = school_id
    return headers

def get_student_id(token):
    """Get a real student ID from the system"""
    headers = get_headers(token, SCHOOL_ID)
    resp = requests.get(f"{API_URL}/students", headers=headers, params={"school_id": SCHOOL_ID})
    if resp.status_code != 200:
        raise Exception(f"Failed to get students: {resp.status_code}")
    students = resp.json()
    if not students:
        raise Exception("No students found")
    return students[0]['id']

def create_payment_body(student_id, discount=0, discount_reason=None, application_image=None):
    """Create a payment request body"""
    body = {
        "school_id": SCHOOL_ID,
        "student_id": student_id,
        "items": [
            {"fee_head_id": "test-head", "fee_head_name": "Tuition Fee", "amount": 1000.0, "period": "April 2026"}
        ],
        "discount": discount,
        "late_fee": 0,
        "payment_mode": "cash"
    }
    if discount_reason:
        body["discount_reason"] = discount_reason
    if application_image:
        body["application_image"] = application_image
    return body

print("=" * 80)
print("TWO-STAGE DISCOUNT APPROVAL WORKFLOW TEST")
print("=" * 80)
print()

# ============================================================================
# SECTION A: POST /api/payments/collect - Application Image Validation
# ============================================================================
print("SECTION A: POST /api/payments/collect - Application Image Validation")
print("-" * 80)

try:
    super_token, super_user = login(SUPER_ADMIN)
    student_id = get_student_id(super_token)
    headers = get_headers(super_token, SCHOOL_ID)
    
    # A1: discount>0, NO application_image → 400
    print("\nA1: Super admin with discount but NO application_image")
    body = create_payment_body(student_id, discount=200, discount_reason="test")
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=headers)
    if resp.status_code == 400 and "application is required" in resp.json().get('detail', '').lower():
        log_test("A1: Missing application_image returns 400", True, f"Got: {resp.json()['detail']}")
    else:
        log_test("A1: Missing application_image returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    
    # A2: discount>0, application_image is NOT a data URL → 400
    print("\nA2: Super admin with discount but invalid application_image (not a data URL)")
    body = create_payment_body(student_id, discount=200, discount_reason="test", application_image="just-a-plain-string")
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=headers)
    if resp.status_code == 400 and ("image or pdf" in resp.json().get('detail', '').lower()):
        log_test("A2: Invalid application_image returns 400", True, f"Got: {resp.json()['detail']}")
    else:
        log_test("A2: Invalid application_image returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    
    # A3: discount>0, valid application_image → 200 with pending_approval
    print("\nA3: Super admin with discount and valid application_image")
    body = create_payment_body(student_id, discount=200, discount_reason="test", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'pending_approval' and data.get('approval_id') and data.get('approval', {}).get('application_image'):
            log_test("A3: Valid discount request returns pending_approval", True, f"approval_id: {data['approval_id']}")
            APPROVAL_1 = data['approval_id']
        else:
            log_test("A3: Valid discount request returns pending_approval", False, f"Missing expected fields: {data}")
    else:
        log_test("A3: Valid discount request returns pending_approval", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    
    # A4: discount=0 (no discount) → 200 with success and receipt_number (regression)
    print("\nA4: Super admin with NO discount (regression)")
    body = create_payment_body(student_id, discount=0)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'success' and data.get('receipt_number'):
            log_test("A4: No discount returns immediate receipt", True, f"receipt: {data['receipt_number']}")
        else:
            log_test("A4: No discount returns immediate receipt", False, f"Missing status=success or receipt_number: {data}")
    else:
        log_test("A4: No discount returns immediate receipt", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    
    # A5: Accountant with discount>0 → 403 (accountant discount block)
    print("\nA5: Accountant with discount (should be blocked)")
    acc_token, acc_user = login(ACCOUNTANT)
    acc_headers = get_headers(acc_token, SCHOOL_ID)
    body = create_payment_body(student_id, discount=100, discount_reason="x", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=acc_headers)
    if resp.status_code == 403:
        log_test("A5: Accountant discount blocked with 403", True, f"Got: {resp.json().get('detail', '')}")
    else:
        log_test("A5: Accountant discount blocked with 403", False, f"Expected 403, got {resp.status_code}: {resp.text}")

except Exception as e:
    log_test("SECTION A", False, f"Exception: {str(e)}")
    print(f"ERROR in Section A: {e}")

# ============================================================================
# SECTION B: POST /api/discount-approvals/{id}/approve - Owner Approval
# ============================================================================
print("\n" + "=" * 80)
print("SECTION B: POST /api/discount-approvals/{id}/approve - Owner Approval")
print("-" * 80)

try:
    owner_token, owner_user = login(OWNER)
    owner_headers = get_headers(owner_token, SCHOOL_ID)
    super_token, super_user = login(SUPER_ADMIN)
    super_headers = get_headers(super_token, SCHOOL_ID)
    student_id = get_student_id(super_token)
    
    # B1: Create approval, owner approves WITHOUT approved_discount → approved_discount = requested discount
    print("\nB1: Owner approves without specifying approved_discount")
    body = create_payment_body(student_id, discount=200, discount_reason="test B1", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_b1_id = resp.json()['approval_id']
        # Get subtotal from approval
        approval_resp = requests.get(f"{API_URL}/discount-approvals/{approval_b1_id}", headers=owner_headers)
        approval_data = approval_resp.json()
        subtotal = approval_data.get('subtotal', 0)
        late_fee = approval_data.get('late_fee', 0)
        requested_discount = approval_data.get('discount', 0)
        
        # Owner approves without approved_discount
        approve_body = {"remark": "OK"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_b1_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 200:
            data = resp.json()
            if (data.get('status') == 'approved' and 
                data.get('approved_discount') == requested_discount and
                data.get('total') == subtotal + late_fee - requested_discount):
                log_test("B1: Approve without approved_discount uses requested discount", True, 
                        f"approved_discount={data['approved_discount']}, total={data['total']}")
                APPROVAL_B1 = approval_b1_id
                # Verify no payment_id yet
                approval_check = requests.get(f"{API_URL}/discount-approvals/{approval_b1_id}", headers=owner_headers)
                if approval_check.status_code == 200:
                    approval_doc = approval_check.json()
                    if not approval_doc.get('payment_id'):
                        log_test("B1: No payment_id set after approve", True)
                    else:
                        log_test("B1: No payment_id set after approve", False, f"payment_id found: {approval_doc.get('payment_id')}")
            else:
                log_test("B1: Approve without approved_discount uses requested discount", False, f"Unexpected response: {data}")
        else:
            log_test("B1: Approve without approved_discount uses requested discount", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    else:
        log_test("B1: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # B2: Create approval, owner approves with REDUCED approved_discount
    print("\nB2: Owner approves with reduced approved_discount")
    body = create_payment_body(student_id, discount=200, discount_reason="test B2", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_b2_id = resp.json()['approval_id']
        # Get approval details
        approval_resp = requests.get(f"{API_URL}/discount-approvals/{approval_b2_id}", headers=owner_headers)
        approval_data = approval_resp.json()
        subtotal = approval_data.get('subtotal', 0)
        late_fee = approval_data.get('late_fee', 0)
        
        # Owner approves with reduced discount
        approve_body = {"remark": "reduced", "approved_discount": 50}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_b2_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 200:
            data = resp.json()
            expected_total = subtotal + late_fee - 50
            if (data.get('status') == 'approved' and 
                data.get('approved_discount') == 50.0 and
                data.get('total') == expected_total):
                log_test("B2: Approve with reduced approved_discount", True, 
                        f"approved_discount=50, total={data['total']}")
                APPROVAL_B2 = approval_b2_id
            else:
                log_test("B2: Approve with reduced approved_discount", False, f"Unexpected response: {data}")
        else:
            log_test("B2: Approve with reduced approved_discount", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    else:
        log_test("B2: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # B3: Create approval, owner approves with approved_discount=0 → 400
    print("\nB3: Owner approves with approved_discount=0 (should reject)")
    body = create_payment_body(student_id, discount=200, discount_reason="test B3", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_b3_id = resp.json()['approval_id']
        approve_body = {"remark": "zero", "approved_discount": 0}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_b3_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 400:
            log_test("B3: Approve with approved_discount=0 returns 400", True, f"Got: {resp.json().get('detail', '')}")
        else:
            log_test("B3: Approve with approved_discount=0 returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("B3: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # B4: Create approval, owner approves with approved_discount > subtotal+late_fee → 400
    print("\nB4: Owner approves with approved_discount > subtotal+late_fee")
    body = create_payment_body(student_id, discount=200, discount_reason="test B4", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_b4_id = resp.json()['approval_id']
        approve_body = {"remark": "too much", "approved_discount": 99999}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_b4_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 400:
            log_test("B4: Approve with excessive approved_discount returns 400", True, f"Got: {resp.json().get('detail', '')}")
        else:
            log_test("B4: Approve with excessive approved_discount returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("B4: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # B5: Accountant tries to approve → 403
    print("\nB5: Accountant tries to approve (should be forbidden)")
    body = create_payment_body(student_id, discount=200, discount_reason="test B5", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_b5_id = resp.json()['approval_id']
        acc_token, acc_user = login(ACCOUNTANT)
        acc_headers = get_headers(acc_token, SCHOOL_ID)
        approve_body = {"remark": "accountant"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_b5_id}/approve", json=approve_body, headers=acc_headers)
        if resp.status_code == 403:
            log_test("B5: Accountant cannot approve (403)", True)
        else:
            log_test("B5: Accountant cannot approve (403)", False, f"Expected 403, got {resp.status_code}: {resp.text}")
    else:
        log_test("B5: Create approval for test", False, f"Failed to create approval: {resp.status_code}")

except Exception as e:
    log_test("SECTION B", False, f"Exception: {str(e)}")
    print(f"ERROR in Section B: {e}")

# ============================================================================
# SECTION C: POST /api/discount-approvals/{id}/collect - Collect Payment
# ============================================================================
print("\n" + "=" * 80)
print("SECTION C: POST /api/discount-approvals/{id}/collect - Collect Payment")
print("-" * 80)

try:
    super_token, super_user = login(SUPER_ADMIN)
    super_headers = get_headers(super_token, SCHOOL_ID)
    owner_token, owner_user = login(OWNER)
    owner_headers = get_headers(owner_token, SCHOOL_ID)
    student_id = get_student_id(super_token)
    
    # C1: Create approved approval, collect as super_admin
    print("\nC1: Collect approved approval as super_admin")
    body = create_payment_body(student_id, discount=200, discount_reason="test C1", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_c1_id = resp.json()['approval_id']
        # Owner approves
        approve_body = {"remark": "OK"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_c1_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 200:
            # Super admin collects
            collect_body = {"payment_mode": "cash"}
            resp = requests.post(f"{API_URL}/discount-approvals/{approval_c1_id}/collect", json=collect_body, headers=super_headers)
            if resp.status_code == 200:
                data = resp.json()
                if (data.get('status') == 'collected' and 
                    data.get('payment_id') and 
                    data.get('receipt_number')):
                    log_test("C1: Collect approved approval returns collected", True, 
                            f"payment_id={data['payment_id']}, receipt={data['receipt_number']}")
                    PAYMENT_ID = data['payment_id']
                    
                    # Verify approval doc updated
                    approval_check = requests.get(f"{API_URL}/discount-approvals/{approval_c1_id}", headers=super_headers)
                    if approval_check.status_code == 200:
                        approval_doc = approval_check.json()
                        if (approval_doc.get('status') == 'collected' and
                            approval_doc.get('payment_id') == PAYMENT_ID and
                            approval_doc.get('receipt_number') and
                            approval_doc.get('collected_by_name') and
                            approval_doc.get('collected_at')):
                            log_test("C1: Approval doc updated with collected status", True)
                        else:
                            log_test("C1: Approval doc updated with collected status", False, f"Missing fields: {approval_doc}")
                else:
                    log_test("C1: Collect approved approval returns collected", False, f"Missing fields: {data}")
            else:
                log_test("C1: Collect approved approval returns collected", False, f"Expected 200, got {resp.status_code}: {resp.text}")
        else:
            log_test("C1: Owner approve", False, f"Failed to approve: {resp.status_code}")
    else:
        log_test("C1: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # C2: Try to collect the same approval again → 400
    print("\nC2: Try to collect already-collected approval")
    if 'approval_c1_id' in locals():
        collect_body = {"payment_mode": "cash"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_c1_id}/collect", json=collect_body, headers=super_headers)
        if resp.status_code == 400:
            log_test("C2: Collect already-collected returns 400", True, f"Got: {resp.json().get('detail', '')}")
        else:
            log_test("C2: Collect already-collected returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("C2: Collect already-collected returns 400", False, "C1 approval not available")
    
    # C3: Try to collect pending approval → 400
    print("\nC3: Try to collect pending approval (not approved yet)")
    body = create_payment_body(student_id, discount=200, discount_reason="test C3", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_c3_id = resp.json()['approval_id']
        collect_body = {"payment_mode": "cash"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_c3_id}/collect", json=collect_body, headers=super_headers)
        if resp.status_code == 400:
            log_test("C3: Collect pending approval returns 400", True, f"Got: {resp.json().get('detail', '')}")
        else:
            log_test("C3: Collect pending approval returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("C3: Create pending approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # C4: Try to collect rejected approval → 400
    print("\nC4: Try to collect rejected approval")
    body = create_payment_body(student_id, discount=200, discount_reason="test C4", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_c4_id = resp.json()['approval_id']
        # Owner rejects
        reject_body = {"remark": "rejected"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_c4_id}/reject", json=reject_body, headers=owner_headers)
        if resp.status_code == 200:
            # Try to collect
            collect_body = {"payment_mode": "cash"}
            resp = requests.post(f"{API_URL}/discount-approvals/{approval_c4_id}/collect", json=collect_body, headers=super_headers)
            if resp.status_code == 400:
                log_test("C4: Collect rejected approval returns 400", True, f"Got: {resp.json().get('detail', '')}")
            else:
                log_test("C4: Collect rejected approval returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
        else:
            log_test("C4: Owner reject", False, f"Failed to reject: {resp.status_code}")
    else:
        log_test("C4: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # C5: Owner tries to collect → 403
    print("\nC5: Owner tries to collect (should be forbidden)")
    body = create_payment_body(student_id, discount=200, discount_reason="test C5", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_c5_id = resp.json()['approval_id']
        # Owner approves
        approve_body = {"remark": "OK"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_c5_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 200:
            # Owner tries to collect
            collect_body = {"payment_mode": "cash"}
            resp = requests.post(f"{API_URL}/discount-approvals/{approval_c5_id}/collect", json=collect_body, headers=owner_headers)
            if resp.status_code == 403:
                log_test("C5: Owner cannot collect (403)", True)
            else:
                log_test("C5: Owner cannot collect (403)", False, f"Expected 403, got {resp.status_code}: {resp.text}")
        else:
            log_test("C5: Owner approve", False, f"Failed to approve: {resp.status_code}")
    else:
        log_test("C5: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # C6: Verify Payment doc has correct fields
    print("\nC6: Verify Payment doc has discount_approval_id and discount_approved_by_name")
    if 'PAYMENT_ID' in locals():
        resp = requests.get(f"{API_URL}/payments/{PAYMENT_ID}", headers=super_headers)
        if resp.status_code == 200:
            payment = resp.json()
            # Get approval to check total
            approval_resp = requests.get(f"{API_URL}/discount-approvals/{approval_c1_id}", headers=super_headers)
            approval = approval_resp.json()
            expected_total = approval.get('total')
            
            if (payment.get('discount_approval_id') and
                payment.get('discount_approved_by_name') and
                abs(payment.get('total_paid', 0) - expected_total) < 0.01):
                log_test("C6: Payment doc has correct approval fields", True, 
                        f"total_paid={payment['total_paid']}, approved_by={payment['discount_approved_by_name']}")
            else:
                log_test("C6: Payment doc has correct approval fields", False, f"Missing or incorrect fields: {payment}")
        else:
            log_test("C6: Get payment doc", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    else:
        log_test("C6: Verify Payment doc", False, "PAYMENT_ID not available from C1")
    
    # C7: Verify receipt PDF download works
    print("\nC7: Verify receipt PDF download (regression)")
    if 'PAYMENT_ID' in locals():
        resp = requests.get(f"{API_URL}/payments/{PAYMENT_ID}/receipt.pdf", headers=super_headers)
        if resp.status_code == 200:
            if (resp.headers.get('content-type') == 'application/pdf' and
                len(resp.content) > 500 and
                resp.content[:4] == b'%PDF'):
                log_test("C7: Receipt PDF download works", True, f"PDF size: {len(resp.content)} bytes")
            else:
                log_test("C7: Receipt PDF download works", False, f"Invalid PDF: content-type={resp.headers.get('content-type')}, size={len(resp.content)}")
        else:
            log_test("C7: Receipt PDF download", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    else:
        log_test("C7: Receipt PDF download", False, "PAYMENT_ID not available from C1")

except Exception as e:
    log_test("SECTION C", False, f"Exception: {str(e)}")
    print(f"ERROR in Section C: {e}")

# ============================================================================
# SECTION D: GET /api/discount-approvals/awaiting-collection-count
# ============================================================================
print("\n" + "=" * 80)
print("SECTION D: GET /api/discount-approvals/awaiting-collection-count")
print("-" * 80)

try:
    super_token, super_user = login(SUPER_ADMIN)
    super_headers = get_headers(super_token, SCHOOL_ID)
    owner_token, owner_user = login(OWNER)
    owner_headers = get_headers(owner_token, SCHOOL_ID)
    student_id = get_student_id(super_token)
    
    # D1: Get current count, create and approve approval, verify count increased
    print("\nD1: Awaiting collection count increases after approval")
    resp = requests.get(f"{API_URL}/discount-approvals/awaiting-collection-count", headers=super_headers)
    if resp.status_code == 200:
        initial_count = resp.json().get('count', 0)
        log_test("D1: Get initial awaiting-collection-count", True, f"count={initial_count}")
        
        # Create and approve approval
        body = create_payment_body(student_id, discount=200, discount_reason="test D1", application_image=TINY_PNG)
        resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
        if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
            approval_d1_id = resp.json()['approval_id']
            # Owner approves
            approve_body = {"remark": "OK"}
            resp = requests.post(f"{API_URL}/discount-approvals/{approval_d1_id}/approve", json=approve_body, headers=owner_headers)
            if resp.status_code == 200:
                # Check count again
                resp = requests.get(f"{API_URL}/discount-approvals/awaiting-collection-count", headers=super_headers)
                if resp.status_code == 200:
                    new_count = resp.json().get('count', 0)
                    if new_count == initial_count + 1:
                        log_test("D1: Count increased after approval", True, f"count={new_count}")
                    else:
                        log_test("D1: Count increased after approval", False, f"Expected {initial_count + 1}, got {new_count}")
                else:
                    log_test("D1: Get count after approval", False, f"Expected 200, got {resp.status_code}")
            else:
                log_test("D1: Owner approve", False, f"Failed to approve: {resp.status_code}")
        else:
            log_test("D1: Create approval", False, f"Failed to create approval: {resp.status_code}")
    else:
        log_test("D1: Get initial awaiting-collection-count", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    
    # D2: Collect the approval, verify count decreased
    print("\nD2: Awaiting collection count decreases after collection")
    if 'approval_d1_id' in locals():
        resp = requests.get(f"{API_URL}/discount-approvals/awaiting-collection-count", headers=super_headers)
        if resp.status_code == 200:
            before_collect_count = resp.json().get('count', 0)
            # Collect
            collect_body = {"payment_mode": "cash"}
            resp = requests.post(f"{API_URL}/discount-approvals/{approval_d1_id}/collect", json=collect_body, headers=super_headers)
            if resp.status_code == 200:
                # Check count again
                resp = requests.get(f"{API_URL}/discount-approvals/awaiting-collection-count", headers=super_headers)
                if resp.status_code == 200:
                    after_collect_count = resp.json().get('count', 0)
                    if after_collect_count == before_collect_count - 1:
                        log_test("D2: Count decreased after collection", True, f"count={after_collect_count}")
                    else:
                        log_test("D2: Count decreased after collection", False, f"Expected {before_collect_count - 1}, got {after_collect_count}")
                else:
                    log_test("D2: Get count after collection", False, f"Expected 200, got {resp.status_code}")
            else:
                log_test("D2: Collect approval", False, f"Failed to collect: {resp.status_code}")
        else:
            log_test("D2: Get count before collection", False, f"Expected 200, got {resp.status_code}")
    else:
        log_test("D2: Count decreased after collection", False, "approval_d1_id not available")

except Exception as e:
    log_test("SECTION D", False, f"Exception: {str(e)}")
    print(f"ERROR in Section D: {e}")

# ============================================================================
# SECTION E: Regression Tests
# ============================================================================
print("\n" + "=" * 80)
print("SECTION E: Regression Tests")
print("-" * 80)

try:
    super_token, super_user = login(SUPER_ADMIN)
    super_headers = get_headers(super_token, SCHOOL_ID)
    owner_token, owner_user = login(OWNER)
    owner_headers = get_headers(owner_token, SCHOOL_ID)
    acc_token, acc_user = login(ACCOUNTANT)
    acc_headers = get_headers(acc_token, SCHOOL_ID)
    student_id = get_student_id(super_token)
    
    # E1: Owner reject a pending approval
    print("\nE1: Owner reject a pending approval")
    body = create_payment_body(student_id, discount=200, discount_reason="test E1", application_image=TINY_PNG)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=super_headers)
    if resp.status_code == 200 and resp.json().get('status') == 'pending_approval':
        approval_e1_id = resp.json()['approval_id']
        reject_body = {"remark": "rejected"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_e1_id}/reject", json=reject_body, headers=owner_headers)
        if resp.status_code == 200 and resp.json().get('status') == 'rejected':
            log_test("E1: Owner reject returns status=rejected", True)
            # Verify no payment created
            approval_resp = requests.get(f"{API_URL}/discount-approvals/{approval_e1_id}", headers=owner_headers)
            if approval_resp.status_code == 200:
                approval = approval_resp.json()
                if not approval.get('payment_id'):
                    log_test("E1: No payment created after rejection", True)
                else:
                    log_test("E1: No payment created after rejection", False, f"payment_id found: {approval.get('payment_id')}")
        else:
            log_test("E1: Owner reject returns status=rejected", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    else:
        log_test("E1: Create approval for test", False, f"Failed to create approval: {resp.status_code}")
    
    # E2: Owner tries to approve already-rejected approval → 400
    print("\nE2: Owner tries to approve already-rejected approval")
    if 'approval_e1_id' in locals():
        approve_body = {"remark": "try to approve"}
        resp = requests.post(f"{API_URL}/discount-approvals/{approval_e1_id}/approve", json=approve_body, headers=owner_headers)
        if resp.status_code == 400:
            log_test("E2: Approve rejected approval returns 400", True, f"Got: {resp.json().get('detail', '')}")
        else:
            log_test("E2: Approve rejected approval returns 400", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("E2: Approve rejected approval", False, "approval_e1_id not available")
    
    # E3: GET /api/discount-approvals?status=collected
    print("\nE3: GET /api/discount-approvals?status=collected")
    resp = requests.get(f"{API_URL}/discount-approvals", headers=super_headers, params={"status": "collected"})
    if resp.status_code == 200:
        approvals = resp.json()
        if isinstance(approvals, list):
            collected_count = len([a for a in approvals if a.get('status') == 'collected'])
            log_test("E3: GET approvals with status=collected", True, f"Found {collected_count} collected approvals")
        else:
            log_test("E3: GET approvals with status=collected", False, f"Expected list, got: {type(approvals)}")
    else:
        log_test("E3: GET approvals with status=collected", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    
    # E4: GET /api/discount-approvals/pending-count still works
    print("\nE4: GET /api/discount-approvals/pending-count (regression)")
    resp = requests.get(f"{API_URL}/discount-approvals/pending-count", headers=owner_headers)
    if resp.status_code == 200:
        data = resp.json()
        if 'count' in data and isinstance(data['count'], int):
            log_test("E4: GET pending-count returns count", True, f"count={data['count']}")
        else:
            log_test("E4: GET pending-count returns count", False, f"Invalid response: {data}")
    else:
        log_test("E4: GET pending-count", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    
    # E5: Non-discount payment by accountant still works
    print("\nE5: Non-discount payment by accountant (regression)")
    body = create_payment_body(student_id, discount=0)
    resp = requests.post(f"{API_URL}/payments/collect", json=body, headers=acc_headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'success' and data.get('receipt_number'):
            log_test("E5: Accountant non-discount payment works", True, f"receipt={data['receipt_number']}")
        else:
            log_test("E5: Accountant non-discount payment works", False, f"Missing status=success or receipt_number: {data}")
    else:
        log_test("E5: Accountant non-discount payment works", False, f"Expected 200, got {resp.status_code}: {resp.text}")

except Exception as e:
    log_test("SECTION E", False, f"Exception: {str(e)}")
    print(f"ERROR in Section E: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total tests: {tests_passed + tests_failed}")
print(f"Passed: {tests_passed}")
print(f"Failed: {tests_failed}")
print(f"Success rate: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")
print()

if tests_failed > 0:
    print("FAILED TESTS:")
    for result in test_results:
        if "✗ FAIL" in result:
            print(f"  {result}")
    print()

print("=" * 80)
